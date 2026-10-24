from __future__ import annotations

import time
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from urllib.parse import quote

import typer
from semantic_version import NpmSpec, Version

from airlock import github, proc
from airlock.contracts import WORKSPACE_PACKAGES, NpmArchive, NpmPackage
from airlock.registries import is_npm_available, is_published
from airlock.targets import load_targets

if TYPE_CHECKING:
    from airlock.contracts import ReleaseTarget

DEPENDENCY_POLL_ATTEMPTS = 61


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


def wait_for_dependencies(dependencies: list[ReleaseTarget]) -> None:
    if not dependencies:
        return
    pending = dependencies
    typer.echo(
        "Waiting for npm dependencies: " + ", ".join(f"{target.spec.label}@{target.version}" for target in pending)
    )
    for attempt in range(DEPENDENCY_POLL_ATTEMPTS):
        pending = [target for target in pending if not is_npm_available(target)]
        if not pending:
            return
        if attempt < DEPENDENCY_POLL_ATTEMPTS - 1:
            time.sleep(10)
    raise ValueError(
        "npm dependencies did not become available: "
        + ", ".join(f"{target.spec.label}@{target.version}" for target in pending)
    )


def publish_npm(targets: list[ReleaseTarget]) -> None:
    if not targets:
        return
    with TemporaryDirectory(prefix="airlock-npm-") as directory:
        archives = {target.spec.label: Path(directory) / f"{quote(target.tag, safe='')}.tgz" for target in targets}
        dependencies = {}
        for target in targets:
            manifest = NpmPackage.model_validate_json((target.directory / "package.json").read_text(encoding="utf-8"))
            if {"prepublishOnly", "publish", "postpublish"}.intersection(manifest.scripts):
                msg = (
                    f"{target.spec.label}: archive publication requires prepack/prepare/postpack hooks; "
                    "publish-only hooks are unsupported"
                )
                raise ValueError(msg)
            archive = archives[target.spec.label]
            proc.run("pnpm", "pack", "--out", str(archive), cwd=target.directory)
            dependencies[target.spec.label] = load_dependencies(target, archive)
        selected = {target.spec.label: target for target in targets}
        graph = {
            target.spec.label: [dep.spec.label for dep in dependencies[target.spec.label] if dep.spec.label in selected]
            for target in targets
        }
        try:
            ordered = list(TopologicalSorter(graph).static_order())
        except CycleError as exc:
            msg = "cyclic production workspace dependency"
            raise ValueError(msg) from exc
        for label in ordered:
            target = selected[label]
            wait_for_dependencies(dependencies[label])
            proc.run(
                "pnpm",
                "publish",
                str(archives[label]),
                "--publish-wait-timeout",
                "0",
                cwd=target.directory,
                interactive=True,
            )
            wait_for_dependencies([target])


def validate_workspaces(targets: list[ReleaseTarget]) -> None:
    workspaces = WORKSPACE_PACKAGES.validate_json(
        proc.run("pnpm", "list", "--recursive", "--depth", "-1", "--json", cwd=proc.find_root())
    )
    for target in targets:
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


def publish_npm_targets(releases: list[tuple[ReleaseTarget, str]]) -> None:
    if not releases:
        return
    validate_workspaces([target for target, _ in releases])
    pending = []
    for target, _ in releases:
        if is_published(target):
            wait_for_dependencies([target])
        else:
            pending.append(target)
    publish_npm(pending)
    head = proc.run("git", "rev-parse", "HEAD")
    for target, notes in releases:
        if github.load_release(target.tag) is None:
            github.create_release(target.tag, notes, head)
