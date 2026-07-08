"""Dead-code ban for the JS/TS workspace: cerberus itself runs fallow's
dead-code analysis (unused files, exports, dependencies, and circular
imports) over the checkout and fails on any finding. Severity thresholds and
ignores are the repo's business via fallow's own config file
(`.fallowrc.json` / `fallow.toml`); cerberus only demands a clean exit.
`--quiet --fail-on-issues` makes the run non-interactive with the verdict in
the exit code. Fallow analyzes only TypeScript/JavaScript, so a repo without
a `package.json` is out of scope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus import proc
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "no-dead-code"
SUMMARY = "fallow finds no unused files, exports, dependencies, or circular imports in the JS/TS workspace"
SCOPE = Scope.CONTENT

_FALLOW_ARGV = ["bunx", "fallow", "dead-code", "--quiet", "--fail-on-issues"]


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    if ctx.file(repo, "package.json") is None:
        res.skip("no package.json")
        return res
    try:
        outcome = proc.run(list(_FALLOW_ARGV), cwd=ctx.source.root)
    except proc.ToolNotFoundError as exc:
        res.error(str(exc))
        return res
    if outcome.returncode == 0:
        res.ok("fallow found no dead code or circular dependencies")
    else:
        res.fail(f"fallow found dead code (exit {outcome.returncode}); run `bunx fallow dead-code` locally for details")
    return res
