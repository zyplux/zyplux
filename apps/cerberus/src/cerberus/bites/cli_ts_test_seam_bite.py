"""The cli test seam: a cli app is driven through argv, so its only public
programmatic surface is one root export (the argv entry the bin wraps), and
its user-story tests reach the app exclusively through the test package's
fixture aliases. Cli apps are the TypeScript workspace members with a `bin`;
libraries carry their own seam under `lib_ts_test_seam`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.bites import story_docs, test_seam
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "cli_ts_test_seam"
SUMMARY = "cli apps export only the root seam and their story tests reach workspace code only through fixture aliases"
SCOPE = Scope.CONTENT

_OK_MESSAGE = "every cli app exports only the root seam; story tests reach workspace code only through fixture aliases"


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    paths = ctx.paths(repo)
    packages = story_docs.TS.package_dirs(repo, ctx, paths)
    if not packages:
        res.skip("no TypeScript packages")
        return res

    seam = test_seam.Seam.from_paths(repo, ctx, "cli app", paths)
    cli_apps = [package for package in packages if seam.load_manifest(package).get("bin")]
    if not cli_apps:
        res.skip("no cli apps")
        return res

    for package in sorted(cli_apps):
        seam.check_package(res, package)

    if not res.problems:
        res.ok(_OK_MESSAGE)
    return res
