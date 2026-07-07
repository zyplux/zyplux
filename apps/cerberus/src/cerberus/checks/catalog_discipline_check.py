from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "catalog-discipline"
SUMMARY = "every workspace package.json dependency pins via catalog: or workspace:"
SCOPE = Scope.CONTENT

_DEPENDENCY_KEYS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
_PINNED_PREFIXES = ("catalog:", "workspace:")


def _is_vendored(path: str) -> bool:
    return "node_modules/" in path


def _manifest(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _manifest_paths(paths: list[str]) -> list[str]:
    return [path for path in paths if (path == "package.json" or path.endswith("/package.json")) and not _is_vendored(path)]


def _uncataloged(label: str, manifest: dict[str, Any]) -> list[str]:
    offenders: list[str] = []
    for key in _DEPENDENCY_KEYS:
        deps = manifest.get(key)
        if not isinstance(deps, dict):
            continue
        for name, spec in deps.items():
            if not isinstance(spec, str) or not spec.startswith(_PINNED_PREFIXES):
                offenders.append(f"{label} → {key}.{name} = {spec!r}")
    return offenders


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    root = ctx.file(repo, "package.json")
    if root is None:
        res.skip("no package.json")
        return res
    if "workspaces" not in _manifest(root):
        res.skip("not a workspace")
        return res

    for path in _manifest_paths(ctx.paths(repo)):
        content = ctx.file(repo, path)
        if content is None:
            continue
        for offender in _uncataloged(path, _manifest(content)):
            res.fail(f"dependency not pinned via catalog:/workspace: — {offender}")

    if not res.problems:
        res.ok("every dependency uses catalog: or workspace:")
    return res
