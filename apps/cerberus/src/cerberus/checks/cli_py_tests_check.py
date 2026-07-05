"""The Python cli test seam: a cli app is driven through argv, so its story
tests may only import its root module and the module backing its
`[project.scripts]` entry (needed to drive `CliRunner`-style in-process
testing) — never reach into the rest of the package directly. Python has no
manifest-level `exports` map to additionally police (see `py_test_seam` for
why), so this check is narrower than `cli-ts-tests`: it polices story-test
imports only. Cli apps are the Python workspace members with a non-empty
`[project.scripts]`; libraries carry their own seam under `lib-py-tests`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.checks import py_test_seam, story_docs
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "cli-py-tests"
SUMMARY = "cli apps' story tests import only the root module or their cli entry module (never other internals)"
SCOPE = Scope.CONTENT

_OK_MESSAGE = "every cli app's story tests import only the root module or their cli entry module"


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    paths = ctx.paths(repo)
    packages = story_docs.PY.package_dirs(repo, ctx, paths)
    if not packages:
        res.skip("no Python packages")
        return res

    seam = py_test_seam.Seam.from_paths(repo, ctx, paths)
    cli_apps = [package for package in packages if py_test_seam.is_cli_app(seam.load_manifest(package))]
    if not cli_apps:
        res.skip("no cli apps")
        return res

    for package in sorted(cli_apps):
        seam.check_package(res, package)

    if not res.problems:
        res.ok(_OK_MESSAGE)
    return res
