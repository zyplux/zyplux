"""Python library stories exercise the package root."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.bites import py_test_seam
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "lib_py_test_seam"
SUMMARY = "libraries' story tests import only their root module (never other internals)"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    py_test_seam.run_seam_check(repo, ctx, res, py_test_seam.LIBRARIES)
    return res
