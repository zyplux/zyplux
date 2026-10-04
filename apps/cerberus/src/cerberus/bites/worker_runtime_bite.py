from __future__ import annotations

import tomllib
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from cerberus.architecture import list_packages
from cerberus.graph.parse import parse_typescript
from cerberus.graph.resolve_ts import resolve
from cerberus.model import CheckResult, Scope
from cerberus.ts_syntax import node_text, parse_jsonc, string_literal, walk_nodes
from cerberus.tsconfig import load_paths

if TYPE_CHECKING:
    from tree_sitter import Node

    from cerberus.context import Context
    from cerberus.model import Repo

ID = "worker_runtime"
SUMMARY = "First-party runtime code reachable from Wrangler Worker entries avoids filesystem builtins"
SCOPE = Scope.CONTENT
_FILESYSTEM = {"node:fs", "node:fs/promises", "fs", "fs/promises"}


def _is_type_edge(node: Node) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type in {"type_alias_declaration", "type_annotation", "interface_declaration", "implements_clause"}:
            return True
        parent = parent.parent
    return False


def _runtime_specifiers(path: str, content: str) -> tuple[list[tuple[str, int]], list[int]]:
    refs = []
    computed = []
    for node in walk_nodes(parse_typescript(path, content).root_node):
        source = None
        if _is_type_edge(node):
            continue
        if node.type in {"import_statement", "export_statement"}:
            if any(child.type == "type" for child in node.children):
                continue
            bindings = [child for child in walk_nodes(node) if child.type in {"import_specifier", "export_specifier"}]
            if bindings and all(any(child.type == "type" for child in binding.children) for binding in bindings):
                continue
            source = node.child_by_field_name("source")
        elif node.type == "call_expression" and node_text(node.child_by_field_name("function") or node) == "import":
            arguments = node.child_by_field_name("arguments")
            source = arguments.named_children[0] if arguments is not None and arguments.named_children else None
            if string_literal(source) is None:
                computed.append(node.start_point.row + 1)
        specifier = string_literal(source)
        if specifier is not None:
            refs.append((specifier, node.start_point.row + 1))
    return refs, computed


def _resolve_paths(path: str, specifier: str, repo: Repo, ctx: Context, gaps: set[str]) -> str | None:
    directory = PurePosixPath(path).parent
    for parent in (directory, *directory.parents):
        config_path = (parent / "tsconfig.json").as_posix()
        if ctx.file(repo, config_path) is None:
            continue
        aliases, _ = load_paths(repo, ctx, config_path, gaps)
        for pattern, targets in aliases.items():
            prefix, wildcard, suffix = pattern.partition("*")
            if specifier != pattern and not (wildcard and specifier.startswith(prefix) and specifier.endswith(suffix)):
                continue
            match = specifier[len(prefix) : len(specifier) - len(suffix) if suffix else None]
            for target in targets:
                found = resolve("tsconfig.json", f"./{target.replace('*', match)}", frozenset(ctx.paths(repo)), {})
                if found is not None:
                    return found
        break
    return None


def _list_entries(repo: Repo, ctx: Context, res: CheckResult, gaps: set[str]) -> list[str]:
    packages = list_packages(repo, ctx)
    paths = frozenset(ctx.paths(repo))
    entries = []
    for path in sorted(paths):
        if PurePosixPath(path).name not in {"wrangler.json", "wrangler.jsonc", "wrangler.toml"}:
            continue
        content = ctx.file(repo, path)
        if content is None:
            res.error(f"cannot read Worker configuration {path}")
            continue
        config = tomllib.loads(content) if path.endswith(".toml") else parse_jsonc(content)
        main = config.get("main")
        if isinstance(main, str):
            if main.startswith(("@", "node_modules/")):
                gaps.add(f"{path}: third-party Worker entry {main} needs bundle validation")
                continue
            entry = resolve(path, f"./{main.removeprefix('./')}", paths, packages)
            if entry is None:
                res.fail(f"{path}: Worker main {main} cannot be resolved")
            else:
                entries.append(entry)
        else:
            gaps.add(f"{path}: framework supplies the Worker entry; configure main to inspect its runtime graph")
    return entries


def _trace_runtime(repo: Repo, ctx: Context, res: CheckResult, entries: list[str], gaps: set[str]) -> int:
    packages = list_packages(repo, ctx)
    paths = frozenset(ctx.paths(repo))
    pending = list(entries)
    visited = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        content = ctx.file(repo, path)
        if content is None:
            res.error(f"cannot read Worker runtime module {path}")
            continue
        refs, computed = _runtime_specifiers(path, content)
        gaps.update(f"{path}:{line}: computed dynamic import cannot be resolved statically" for line in computed)
        for specifier, line in refs:
            if specifier in _FILESYSTEM:
                res.fail(f"{path}:{line}: Worker runtime reaches {specifier}")
                continue
            target = resolve(path, specifier, paths, packages) or _resolve_paths(path, specifier, repo, ctx, gaps)
            if target is not None:
                pending.append(target)
            elif specifier.startswith((".", "#", "@/")) or any(
                specifier == name or specifier.startswith(f"{name}/") for name in packages
            ):
                res.fail(f"{path}:{line}: first-party runtime import {specifier} cannot be resolved")
            elif not specifier.startswith("node:"):
                gaps.add(f"third-party runtime {specifier} is outside the first-party graph")
    return len(visited)


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    gaps: set[str] = set()
    entries = _list_entries(repo, ctx, res, gaps)
    visited = _trace_runtime(repo, ctx, res, entries, gaps)
    res.verbose_lines = sorted(gaps)
    res.detail = f"visited {visited} first-party runtime modules; {len(gaps)} static coverage limits"
    if not res.problems:
        if entries:
            res.ok(res.detail)
        else:
            res.skip(
                "no explicit Wrangler Worker main entries"
                + (f"; {len(gaps)} framework entries need bundle validation" if gaps else "")
            )
    return res
