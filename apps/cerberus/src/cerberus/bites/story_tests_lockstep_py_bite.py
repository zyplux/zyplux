from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.bites import story_docs
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "story_tests_lockstep_py"
SUMMARY = "every ### criterion header in tests/**/stories/*.md has a matching, title-matched pytest test"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    story_docs.run_story_check(repo, ctx, res, story_docs.PY)
    return res
