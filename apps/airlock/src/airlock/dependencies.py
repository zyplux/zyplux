from __future__ import annotations

from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING

import httpx

from airlock import npm_dependencies, pypi
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
    expected = sorted(dependency.tag for dependency in dependencies)
    if target.spec.requires is None or sorted(target.spec.requires) != expected:
        msg = f"{target.spec.label}: prepared dependencies differ from package contents; run airlock prepare"
        raise ValueError(msg)


def load_prepared_dependencies(target: ReleaseTarget, targets: dict[str, ReleaseTarget]) -> list[ReleaseTarget]:
    if not isinstance(target.spec, PackageSpec) or target.spec.requires is None:
        msg = f"{target.spec.label}: missing prepared dependencies; run airlock prepare"
        raise ValueError(msg)
    dependencies = []
    for tag in target.spec.requires:
        dependency = targets.get(tag)
        if dependency is None or dependency.spec.kind != target.spec.kind:
            msg = f"{target.spec.label}: unknown package dependency {tag}; run airlock prepare"
            raise ValueError(msg)
        dependencies.append(dependency)
    return dependencies


def validate_dependency_cycles(target: ReleaseTarget, dependencies: list[ReleaseTarget]) -> None:
    targets = {candidate.tag: candidate for candidate in load_targets()}
    graph: dict[str, set[str]] = {}
    pending = [target]
    while pending:
        current = pending.pop()
        if current.tag in graph:
            continue
        neighbors = dependencies if current.tag == target.tag else load_prepared_dependencies(current, targets)
        graph[current.tag] = {dependency.tag for dependency in neighbors}
        pending.extend(neighbors)
    try:
        TopologicalSorter(graph).prepare()
    except CycleError:
        pass
    else:
        return
    unpublished: dict[str, set[str]] = {}
    pending_tags = [target.tag]
    while pending_tags:
        tag = pending_tags.pop()
        if tag in unpublished:
            continue
        try:
            has_published = is_published(targets[tag])
        except httpx.HTTPError:
            # Dependency waiting owns retries and authentication errors.
            return
        unpublished[tag] = set() if has_published else graph[tag]
        pending_tags.extend(unpublished[tag])
    try:
        TopologicalSorter(unpublished).prepare()
    except CycleError as exc:
        msg = f"{target.spec.label}: cyclic production workspace dependency: {exc}"
        raise ValueError(msg) from exc
