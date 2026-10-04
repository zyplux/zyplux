from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.bites import ts_story_docs
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "story_tests_lockstep_ts"
SUMMARY = "TypeScript stories pair with numeric or prefixed criteria in their own directories"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    ts_story_docs.run_story_check(repo, ctx, res)
    return res
