"""Python library stories exercise the package root."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.model import CheckResult, Scope
from cerberus.story_tests import python_test_imports

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "lib_py_test_seam"
SUMMARY = "libraries' story tests import only their root module (never other internals)"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    python_test_imports.run_seam_check(repo, ctx, res, python_test_imports.LIBRARIES)
    return res
