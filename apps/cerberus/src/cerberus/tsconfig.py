from __future__ import annotations

import posixpath
from typing import TYPE_CHECKING

from cerberus.architecture import list_packages
from cerberus.graph.resolve_ts import resolve
from cerberus.ts_syntax import parse_jsonc

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo


def load_paths(
    repo: Repo, ctx: Context, path: str, gaps: set[str], ancestors: frozenset[str] = frozenset()
) -> tuple[dict[str, list[str]], str | None]:
    if path in ancestors:
        message = f"cyclic TypeScript configuration inheritance: {path}"
        raise ValueError(message)
    content = ctx.file(repo, path)
    if content is None:
        gaps.add(f"{path}: external compiler configuration is outside the first-party graph")
        return {}, None
    config = parse_jsonc(content)
    paths = {}
    base = None
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
            inherited_paths, base = load_paths(repo, ctx, inherited, gaps, ancestors | {path})
            paths.update(inherited_paths)
    options = config.get("compilerOptions", {})
    if "baseUrl" in options:
        base = posixpath.normpath(posixpath.join(posixpath.dirname(path), options["baseUrl"]))
    if "paths" in options:
        paths = {
            alias: [posixpath.normpath(posixpath.join(base or posixpath.dirname(path), target)) for target in targets]
            for alias, targets in options["paths"].items()
        }
    return paths, base
