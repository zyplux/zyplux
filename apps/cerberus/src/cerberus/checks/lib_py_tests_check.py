"""The Python library test seam: a library's public interface is its root
module, so its story tests may only import that root module — never reach
into its internals directly. Python has no manifest-level `exports` map to
additionally police (see `py_test_seam` for why), so this check is narrower
than `lib-ts-tests`: it polices story-test imports only. Libraries are the
Python workspace members with no `[project.scripts]` — cli apps carry their
own seam, with an extra entry-module allowance, under `cli-py-tests`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.checks import py_test_seam, story_docs
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "lib-py-tests"
SUMMARY = "libraries' story tests import only their root module (never other internals)"
SCOPE = Scope.CONTENT

_OK_MESSAGE = "every library's story tests import only their root module"


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    paths = ctx.paths(repo)
    packages = story_docs.PY.package_dirs(repo, ctx, paths)
    if not packages:
        res.skip("no Python packages")
        return res

    seam = py_test_seam.Seam.from_paths(repo, ctx, paths)
    libraries = [package for package in packages if not py_test_seam.is_cli_app(seam.load_manifest(package))]
    if not libraries:
        res.skip("no libraries")
        return res

    for package in sorted(libraries):
        seam.check_package(res, package)

    if not res.problems:
        res.ok(_OK_MESSAGE)
    return res
