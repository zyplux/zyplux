from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from semantic_version import NpmSpec, Version

from airlock import proc
from airlock.contracts import WORKSPACE_PACKAGES, NpmArchive
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
    root = proc.find_root(target.directory)
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
        dependencies.append(dependency)
    return dependencies
