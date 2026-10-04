"""Python CLI stories exercise the package root and its declared entry modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.bites import py_test_seam
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "cli_py_test_seam"
SUMMARY = "cli apps' story tests import only the root module or their cli entry module (never other internals)"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    py_test_seam.run_seam_check(repo, ctx, res, py_test_seam.CLI_APPS)
    return res
