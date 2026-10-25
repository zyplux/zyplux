from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import typer
from semantic_version import NpmSpec, Version

from airlock import github, proc
from airlock.content_hash import build_archives, validate_content_hash
from airlock.contracts import WORKSPACE_PACKAGES, NpmArchive, NpmPackage
from airlock.registries import is_published, wait_for_dependencies
from airlock.targets import load_targets

if TYPE_CHECKING:
    from airlock.contracts import ReleaseTarget


def parse_dependency(name: str, specifier: str) -> tuple[str, str]:
    if not specifier.startswith("npm:"):
        return name, specifier
    package_spec = specifier.removeprefix("npm:")
    try:
        NpmSpec(package_spec)
    except ValueError:
        package, separator, version = package_spec.rpartition("@")
        return (package, version) if separator and package else (package_spec, "*")
    return name, package_spec


def matches_dependency(version: str | None, specifier: str) -> bool:
    try:
        return version is not None and NpmSpec(specifier).match(Version(version))
    except ValueError:
        return False


def load_dependencies(target: ReleaseTarget, archive: Path) -> list[ReleaseTarget]:
    manifest = NpmArchive.model_validate_json(proc.run("tar", "-xOf", str(archive), "package/package.json"))
    if manifest.name != target.spec.label or manifest.version != target.version:
        msg = f"{target.spec.label}: packed package identity must match {target.spec.label}@{target.version}"
        raise ValueError(msg)
    bundled = (
        manifest.bundled_dependencies if manifest.bundled_dependencies is not None else manifest.bundle_dependencies
    )
    bundled_names = set(manifest.dependencies) if bundled is True else set(bundled if isinstance(bundled, list) else [])
    requirements = [
        parse_dependency(name, specifier)
        for name, specifier in (manifest.dependencies | manifest.optional_dependencies).items()
        if name not in bundled_names
    ]
    if not requirements:
        return []
    root = proc.find_root()
    configured = {target.directory: target for target in load_targets(root) if target.spec.kind == "npm"}
    workspaces = WORKSPACE_PACKAGES.validate_json(
        proc.run("pnpm", "list", "--recursive", "--depth", "-1", "--json", cwd=root)
    )
    dependencies = []
    for workspace in workspaces:
        if not any(
            workspace.name == name and matches_dependency(workspace.version, specifier)
            for name, specifier in requirements
        ):
            continue
        dependency = configured.get(Path(workspace.path).resolve())
        if dependency is None:
            msg = f"{target.spec.label}: declare an npm target for dependency {workspace.path}"
            raise ValueError(msg)
        if workspace.private:
            msg = f"{target.spec.label}: workspace dependency {workspace.name} is private"
            raise ValueError(msg)
        if workspace.name != dependency.spec.label or workspace.version != dependency.version:
            msg = f"{target.spec.label}: dependency {dependency.spec.label} must match its configured name and version"
            raise ValueError(msg)
        if dependency.spec.label == target.spec.label:
            msg = f"{target.spec.label}: cyclic production workspace dependency"
            raise ValueError(msg)
        dependencies.append(dependency)
    return dependencies


def validate_workspace(target: ReleaseTarget) -> None:
    workspaces = WORKSPACE_PACKAGES.validate_json(
        proc.run("pnpm", "list", "--recursive", "--depth", "-1", "--json", cwd=proc.find_root())
    )
    workspace = next(
        (workspace for workspace in workspaces if Path(workspace.path).resolve() == target.directory), None
    )
    if workspace is None:
        msg = f"{target.spec.label}: {target.directory} is not a pnpm workspace package"
        raise ValueError(msg)
    if workspace.name != target.spec.label:
        msg = f"{target.spec.label}: workspace package name is {workspace.name}"
        raise ValueError(msg)
    if workspace.private:
        msg = f"{target.spec.label}: private workspace packages cannot be published"
        raise ValueError(msg)
    if workspace.version != target.version:
        msg = f"{target.spec.label}: workspace version must be {target.version}"
        raise ValueError(msg)


def publish_npm(target: ReleaseTarget) -> None:
    validate_workspace(target)
    if is_published(target):
        wait_for_dependencies([target])
        if github.load_release(target.tag) is None:
            validate_content_hash(target)
        typer.echo(f"{target.spec.label} {target.version} is already published; nothing to do")
        return
    manifest = NpmPackage.model_validate_json((target.directory / "package.json").read_text(encoding="utf-8"))
    if {"prepublishOnly", "publish", "postpublish"}.intersection(manifest.scripts):
        msg = (
            f"{target.spec.label}: archive publication requires prepack/prepare/postpack hooks; "
            "publish-only hooks are unsupported"
        )
        raise ValueError(msg)
    with TemporaryDirectory(prefix="airlock-npm-") as directory:
        [archive] = build_archives(target, Path(directory))
        validate_content_hash(target, [archive])
        wait_for_dependencies(load_dependencies(target, archive))
        proc.run("pnpm", "publish", str(archive), "--publish-wait-timeout", "0", cwd=target.directory, interactive=True)
        wait_for_dependencies([target])
