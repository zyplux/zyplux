"""Require TypeScript typechecking through project references."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from cerberus.model import CheckResult, Repo, Scope
from cerberus.syntax.shell_commands import expand_pnpm_command, matches_tool_command, read_pnpm_scripts
from cerberus.workspaces.npm_packages import load_workspace_manifest

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "tsc"
SUMMARY = "TypeScript typecheck runs via project references (tsc -b), not a per-package fan-out"
SCOPE = Scope.CONTENT

_TSCONFIG = re.compile(r"(?:^|/)tsconfig[^/]*\.json$")


def _is_vendored(path: str) -> bool:
    return "node_modules/" in path


def _has_tsconfig(paths: list[str]) -> bool:
    return any(_TSCONFIG.search(path) is not None and not _is_vendored(path) for path in paths)


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    root = load_workspace_manifest(repo, ctx, res)
    if root is None:
        return res
    if not _has_tsconfig(ctx.paths(repo)):
        res.skip("no tsconfig")
        return res

    scripts = read_pnpm_scripts(root)
    script = scripts.get("typecheck", "")
    if not script.strip():
        res.fail("no `typecheck` script; expected `tsc -b` (project references)")
        return res
    commands = expand_pnpm_command(("pnpm", "run", "typecheck"), scripts)
    if not any(
        matches_tool_command(command, ("pnpm", "exec", "tsc", flag))
        for command in commands
        for flag in ("-b", "--build")
    ):
        res.fail(f"`typecheck` must run `tsc -b` (project references); found `{script}`")
        return res

    res.ok("typecheck runs via project references")
    return res
