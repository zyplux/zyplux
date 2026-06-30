from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "ts-project-references"
SUMMARY = "TypeScript typecheck runs via project references (tsc -b), not a per-package fan-out"
SCOPE = Scope.CONTENT

_TSCONFIG = re.compile(r"(?:^|/)tsconfig[^/]*\.json$")
_TSC_BUILD = re.compile(r"\btsc\s+(?:-b\b|--build\b)")


def _is_vendored(path: str) -> bool:
    return "node_modules/" in path


def _has_tsconfig(paths: list[str]) -> bool:
    return any(_TSCONFIG.search(path) is not None and not _is_vendored(path) for path in paths)


def _manifest(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    root = ctx.file(repo, "package.json")
    if root is None:
        res.skip("no package.json")
        return res

    manifest = _manifest(root)
    if "workspaces" not in manifest:
        res.skip("not a workspace")
        return res
    if not _has_tsconfig(ctx.paths(repo)):
        res.skip("no tsconfig")
        return res

    scripts = manifest.get("scripts")
    script = scripts.get("typecheck") if isinstance(scripts, dict) else None
    if not isinstance(script, str) or not script.strip():
        res.fail("no `typecheck` script; expected `tsc -b` (project references)")
        return res
    if not _TSC_BUILD.search(script):
        res.fail(f"`typecheck` must run `tsc -b` (project references); found `{script}`")
        return res

    res.ok("typecheck runs via project references")
    return res
