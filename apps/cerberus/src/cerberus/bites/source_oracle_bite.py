from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "source_oracle"
SUMMARY = "source categories are unambiguous and follow their configured nesting rules"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    for path in ctx.paths(repo):
        try:
            ctx.config.source_oracle.classify(path)
        except ValueError as exc:
            res.fail(str(exc))
            return res
    res.ok("source categories are unambiguous and follow their configured nesting rules")
    return res
