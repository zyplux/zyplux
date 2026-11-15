"""Check that Python story criteria and pytest test titles agree."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.model import CheckResult, Repo, Scope
from cerberus.story_tests import python_story_docs

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "story_tests_lockstep_py"
SUMMARY = "every Python story criterion has a matching, title-matched pytest test"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    python_story_docs.run_story_check(repo, ctx, res)
    return res
