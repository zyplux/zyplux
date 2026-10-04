from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from cerberus.architecture import build_export_map, is_library, list_source_targets, run_package_policy
from cerberus.model import Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.graph.resolve_ts import PackageInfo
    from cerberus.model import CheckResult, Repo

ID = "package_exports"
SUMMARY = "Libraries expose a pure root barrel or named module subpaths, with matching published entries"
SCOPE = Scope.CONTENT


def _inspect(_name: str, package: PackageInfo) -> list[str]:
    manifest = package.manifest
    entries = build_export_map(manifest.get("exports"))
    published = build_export_map(manifest.get("publishConfig", {}).get("exports", manifest.get("exports")))
    findings = []
    if set(entries) != set(published):
        findings.append("source and published export keys must agree")
    modules = {key: target for key, target in entries.items() if list_source_targets(target)}
    if is_library(package) and "." in modules and len(modules) > 1:
        findings.append("choose one root barrel or named subpaths; do not mix both library export families")
    for key, target in modules.items():
        for entry in list_source_targets(target):
            if key == "." and is_library(package) and PurePosixPath(entry).stem.removesuffix(".d") != "index":
                findings.append("a library root barrel is named index")
            if "*" in entry or key == ".":
                continue
            if not key.startswith("./") or PurePosixPath(key[2:]).name != PurePosixPath(entry).stem.removesuffix(".d"):
                findings.append(f"{key} must name its source module {PurePosixPath(entry).stem.removesuffix('.d')}")
    return findings


def run(repo: Repo, ctx: Context) -> CheckResult:
    return run_package_policy(repo, ctx, ID, _inspect)
