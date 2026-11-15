"""Python CLI stories exercise the package root and its declared entry modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.model import CheckResult, Scope
from cerberus.story_tests import python_test_imports

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "cli_py_test_seam"
SUMMARY = "cli apps' story tests import only the root module or their cli entry module (never other internals)"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    python_test_imports.run_seam_check(repo, ctx, res, python_test_imports.CLI_APPS)
    return res
