"""Inspect package export targets and apply export policies across a workspace."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from cerberus.model import CheckResult
from cerberus.workspaces.npm_packages import list_packages

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from cerberus.context import Context
    from cerberus.model import Repo
    from cerberus.workspaces.npm_packages import PackageInfo


def build_export_map(exports: object) -> dict[str, Any]:
    if exports is None:
        return {}
    if isinstance(exports, dict) and any(key.startswith(".") for key in exports):
        return exports
    return {".": exports}


def list_targets(target: object) -> list[str]:
    if isinstance(target, str):
        return [target]
    if isinstance(target, dict):
        return [entry for child in target.values() for entry in list_targets(child)]
    if isinstance(target, list):
        return [entry for child in target for entry in list_targets(child)]
    return []


def list_source_targets(exports: object) -> list[str]:
    return [
        target
        for target in list_targets(exports)
        if PurePosixPath(target).suffix in {".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"}
    ]


def run_package_policy(
    repo: Repo, ctx: Context, check_id: str, inspect: Callable[[str, PackageInfo], Iterable[str]]
) -> CheckResult:
    packages = list_packages(repo, ctx)
    res = CheckResult(check_id, repo.name)
    if not packages:
        res.skip("no named TypeScript workspace packages")
        return res
    for name, package in packages.items():
        for finding in inspect(name, package):
            res.fail(f"{package.directory or '.'}/package.json: {finding}")
    if not res.problems:
        res.ok("workspace package policy holds")
    return res
