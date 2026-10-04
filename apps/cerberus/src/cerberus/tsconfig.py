from __future__ import annotations

import posixpath
from typing import TYPE_CHECKING, Any

from cerberus.architecture import list_packages
from cerberus.graph.resolve_ts import resolve
from cerberus.ts_syntax import parse_jsonc

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo


def _load_options(
    repo: Repo, ctx: Context, path: str, gaps: set[str], ancestors: frozenset[str] = frozenset()
) -> dict[str, Any]:
    if path in ancestors:
        message = f"cyclic TypeScript configuration inheritance: {path}"
        raise ValueError(message)
    content = ctx.file(repo, path)
    if content is None:
        gaps.add(f"{path}: external compiler configuration is outside the first-party graph")
        return {}
    config = parse_jsonc(content)
    options = {}
    parents = config.get("extends", [])
    for parent in [parents] if isinstance(parents, str) else parents:
        inherited = resolve(path, parent, frozenset(ctx.paths(repo)), list_packages(repo, ctx))
        if inherited is None and parent.startswith("."):
            inherited = posixpath.normpath(posixpath.join(posixpath.dirname(path), parent))
            if not inherited.endswith(".json"):
                inherited += ".json"
        if inherited is None:
            gaps.add(f"{path}: external compiler configuration {parent} is outside the first-party graph")
        else:
            options.update(_load_options(repo, ctx, inherited, gaps, ancestors | {path}))
    declared = config.get("compilerOptions", {})
    if "baseUrl" in declared:
        declared["baseUrl"] = posixpath.normpath(posixpath.join(posixpath.dirname(path), declared["baseUrl"]))
    if "paths" in declared:
        declared["pathsBasePath"] = posixpath.dirname(path)
    options.update(declared)
    return options


def load_paths(repo: Repo, ctx: Context, path: str, gaps: set[str]) -> tuple[dict[str, list[str]], str | None]:
    options = _load_options(repo, ctx, path, gaps)
    base = options.get("baseUrl")
    origin = base or options.get("pathsBasePath", posixpath.dirname(path))
    return {
        alias: [posixpath.normpath(posixpath.join(origin, target)) for target in targets]
        for alias, targets in options.get("paths", {}).items()
    }, base
