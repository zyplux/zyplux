from __future__ import annotations

import tomllib
import zipfile
from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING

import httpx
from packaging.metadata import Metadata
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from airlock.contracts import PythonProject
from airlock.registries import is_published
from airlock.targets import load_targets

if TYPE_CHECKING:
    from pathlib import Path

    from airlock.contracts import ReleaseTarget


def select_dependencies(requirements: list[Requirement], targets: dict[str, ReleaseTarget]) -> list[ReleaseTarget]:
    return [
        dependency
        for dependency in targets.values()
        if any(
            requirement.url is None
            and canonicalize_name(requirement.name) == canonicalize_name(dependency.spec.label)
            and requirement.specifier.contains(dependency.version, prereleases=True)
            for requirement in requirements
        )
    ]


def load_project_requirements(target: ReleaseTarget) -> list[Requirement]:
    manifest = tomllib.loads((target.directory / "pyproject.toml").read_text(encoding="utf-8"))
    project = PythonProject.model_validate(manifest["project"]) if "project" in manifest else None
    if project is None or {"dependencies", "optional-dependencies"}.intersection(project.dynamic):
        msg = f"{target.spec.label}: publish dynamic workspace dependencies before their consumers"
        raise ValueError(msg)
    dependencies = project.dependencies + [
        dependency for requirements in project.optional_dependencies.values() for dependency in requirements
    ]
    return [Requirement(dependency) for dependency in dependencies]


def validate_dependency_cycles(
    target: ReleaseTarget, dependencies: list[ReleaseTarget], targets: dict[str, ReleaseTarget]
) -> None:
    root = canonicalize_name(target.spec.label)
    graph: dict[str, set[str]] = {}
    pending = [target]
    while pending:
        current = pending.pop()
        name = canonicalize_name(current.spec.label)
        if name in graph:
            continue
        neighbors: list[ReleaseTarget]
        if name == root:
            neighbors = dependencies
        else:
            try:
                has_published = is_published(current)
            except httpx.HTTPError:
                # Dependency waiting owns retries and authentication errors.
                return
            neighbors = [] if has_published else select_dependencies(load_project_requirements(current), targets)
        graph[name] = {canonicalize_name(dependency.spec.label) for dependency in neighbors}
        pending.extend(neighbors)
    try:
        TopologicalSorter(graph).prepare()
    except CycleError as exc:
        msg = f"{target.spec.label}: cyclic production workspace dependency: {exc}"
        raise ValueError(msg) from exc


def load_dependencies(target: ReleaseTarget, archives: list[Path]) -> list[ReleaseTarget]:
    wheels = [archive for archive in archives if archive.suffix == ".whl"]
    if len(wheels) != 1:
        msg = f"{target.spec.label}: Python build must produce exactly one wheel"
        raise ValueError(msg)
    with zipfile.ZipFile(wheels[0]) as wheel:
        files = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        if len(files) != 1:
            msg = f"{target.spec.label}: wheel must contain exactly one METADATA file"
            raise ValueError(msg)
        try:
            metadata = Metadata.from_email(wheel.read(files[0]))
        except ExceptionGroup as exc:
            msg = f"{target.spec.label}: invalid wheel metadata: {exc}"
            raise ValueError(msg) from exc
    if canonicalize_name(metadata.name) != canonicalize_name(target.spec.label) or metadata.version != Version(
        target.version
    ):
        msg = f"{target.spec.label}: wheel identity must match {target.spec.label}@{target.version}"
        raise ValueError(msg)
    requirements = metadata.requires_dist or []
    if not requirements:
        return []
    targets: dict[str, ReleaseTarget] = {
        canonicalize_name(dependency.spec.label): dependency
        for dependency in load_targets()
        if dependency.spec.kind == "pypi"
    }
    dependencies = select_dependencies(requirements, targets)
    validate_dependency_cycles(target, dependencies, targets)
    return dependencies
