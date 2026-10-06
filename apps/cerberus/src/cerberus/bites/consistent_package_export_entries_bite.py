from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from cerberus.architecture import build_export_map, list_source_targets, run_package_policy
from cerberus.graph.parse import parse_typescript
from cerberus.model import Scope
from cerberus.ts_syntax import node_text, string_literal, walk_nodes

if TYPE_CHECKING:
    from tree_sitter import Node

    from cerberus.context import Context
    from cerberus.graph.resolve_ts import PackageInfo
    from cerberus.model import CheckResult, Repo

ID = "consistent_package_export_entries"
SUMMARY = "Workspace exports use index roots or named modules, with matching published entries"
SCOPE = Scope.CONTENT


def _get_property(node: Node | None, name: str) -> Node | None:
    if node is not None and node.type == "object":
        for property_node in node.named_children:
            key = property_node.child_by_field_name("key")
            if key is not None and (string_literal(key) or node_text(key)) == name:
                return property_node.child_by_field_name("value")
    return None


def _find_router_entry(package: PackageInfo, repo: Repo, ctx: Context) -> str | None:
    for extension in ("js", "mjs", "ts", "cjs", "mts", "cts"):
        path = str(PurePosixPath(package.directory) / f"vite.config.{extension}")
        content = ctx.file(repo, path)
        if content is not None:
            break
    else:
        return None
    for node in walk_nodes(parse_typescript(path, content).root_node):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None or node_text(function) != "tanstackStart":
            continue
        arguments = node.child_by_field_name("arguments")
        options = next(iter(arguments.named_children), None) if arguments is not None else None
        entry = _get_property(_get_property(options, "router"), "entry")
        return string_literal(entry) if entry is not None else "router"
    return None


def _inspect(package: PackageInfo, router_entry: str | None) -> list[str]:
    manifest = package.manifest
    entries = build_export_map(manifest.get("exports"))
    published = build_export_map(manifest.get("publishConfig", {}).get("exports", manifest.get("exports")))
    findings = []
    if set(entries) != set(published):
        findings.append("source and published export keys must agree")
    modules = {key: target for key, target in entries.items() if list_source_targets(target)}
    if "." in modules and len(modules) > 1:
        findings.append("choose one root barrel or named subpaths; do not mix both export families")
    for key, target in modules.items():
        for entry in list_source_targets(target):
            if key == "." and PurePosixPath(entry).stem.removesuffix(".d") not in {"index", router_entry}:
                findings.append(
                    "a root barrel is named index; application router roots match their TanStack Vite entry"
                )
            if "*" in entry or key == ".":
                continue
            if not key.startswith("./") or PurePosixPath(key[2:]).name != PurePosixPath(entry).stem.removesuffix(".d"):
                findings.append(f"{key} must name its source module {PurePosixPath(entry).stem.removesuffix('.d')}")
    return findings


def run(repo: Repo, ctx: Context) -> CheckResult:
    return run_package_policy(
        repo, ctx, ID, lambda _name, package: _inspect(package, _find_router_entry(package, repo, ctx))
    )
