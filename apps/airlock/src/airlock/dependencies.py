from __future__ import annotations

from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING

import httpx

from airlock import npm_dependencies, proc, pypi
from airlock.contracts import PackageSpec
from airlock.registries import is_published
from airlock.targets import load_targets

if TYPE_CHECKING:
    from pathlib import Path

    from airlock.contracts import ReleaseTarget


def load_dependencies(target: ReleaseTarget, archives: list[Path]) -> list[ReleaseTarget]:
    if target.spec.kind == "npm":
        [archive] = archives
        return npm_dependencies.load_dependencies(target, archive)
    return pypi.load_dependencies(target, archives)


def validate_prepared_dependencies(target: ReleaseTarget, dependencies: list[ReleaseTarget]) -> None:
    if not isinstance(target.spec, PackageSpec):
        msg = "prepared dependencies require a package target"
        raise TypeError(msg)
    expected = sorted(dependency.spec.name for dependency in dependencies)
    if sorted(target.spec.depends_on) != expected:
        msg = f"{target.package_name}: prepared dependencies differ from package contents; run airlock prepare"
        raise ValueError(msg)


def load_prepared_dependencies(target: ReleaseTarget, targets: dict[str, ReleaseTarget]) -> list[ReleaseTarget]:
    if not isinstance(target.spec, PackageSpec):
        msg = "prepared dependencies require a package target"
        raise TypeError(msg)
    dependencies = []
    for name in target.spec.depends_on:
        dependency = targets.get(name)
        if dependency is None or dependency.spec.kind != target.spec.kind:
            msg = f"{target.package_name}: unknown package dependency {name}; run airlock prepare"
            raise ValueError(msg)
        dependencies.append(dependency)
    return dependencies


def validate_dependency_cycles(target: ReleaseTarget, dependencies: list[ReleaseTarget]) -> None:
    if not dependencies:
        return
    targets = {candidate.spec.name: candidate for candidate in load_targets(proc.find_root(target.directory))}
    graph: dict[str, set[str]] = {}
    pending = [target]
    while pending:
        current = pending.pop()
        name = current.spec.name
        if name in graph:
            continue
        neighbors = dependencies if current.tag == target.tag else load_prepared_dependencies(current, targets)
        graph[name] = {dependency.spec.name for dependency in neighbors}
        pending.extend(neighbors)
    try:
        TopologicalSorter(graph).prepare()
    except CycleError:
        pass
    else:
        return
    unpublished: dict[str, set[str]] = {}
    pending_names = [target.spec.name]
    while pending_names:
        name = pending_names.pop()
        if name in unpublished:
            continue
        try:
            has_published = is_published(targets[name])
        except httpx.HTTPError:
            # Dependency waiting owns retries and authentication errors.
            return
        unpublished[name] = set() if has_published else graph[name]
        pending_names.extend(unpublished[name])
    try:
        TopologicalSorter(unpublished).prepare()
    except CycleError as exc:
        msg = f"{target.package_name}: cyclic production workspace dependency: {exc}"
        raise ValueError(msg) from exc
