"""The Python library test seam: a library's public interface is its root
module, so its story tests may only import that root module — never reach
into its internals directly. Python has no manifest-level `exports` map to
additionally police (see `py_test_seam` for why), so this check is narrower
than `lib_ts_test_seam`: it polices story-test imports only. Libraries are the
Python workspace members with no `[project.scripts]` — cli apps carry their
own seam, with an extra entry-module allowance, under `cli_py_test_seam`.
"""

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
