from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from cerberus import workspaces
from cerberus.graph.resolve_ts import PackageInfo
from cerberus.model import CheckResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from cerberus.context import Context
    from cerberus.model import Repo


def list_packages(repo: Repo, ctx: Context) -> dict[str, PackageInfo]:
    packages = {}
    for directory in workspaces.ts_member_dirs(repo, ctx, ctx.paths(repo)):
        path = f"{directory}/package.json" if directory else "package.json"
        content = ctx.file(repo, path)
        if content is None:
            continue
        manifest = json.loads(content)
        if isinstance(manifest, dict) and isinstance(manifest.get("name"), str):
            packages[manifest["name"]] = PackageInfo(directory, manifest)
    return packages


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


def list_dependencies(manifest: dict[str, Any]) -> set[str]:
    return {
        name
        for category in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
        for name in manifest.get(category, {})
    }


def is_library(package: PackageInfo) -> bool:
    return package.directory.split("/", 1)[0] == "packages"


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
