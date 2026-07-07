"""The library test seam: a library's public interface is its root export, so
its `exports` map exposes nothing beyond the root seam, and its user-story
tests reach it exclusively through the test package's fixture aliases.
Libraries are the TypeScript workspace members without a `bin` — cli apps
carry their own seam under `cli-ts-tests`. A private package outside `tests/`
is still an importable surface for its sibling workspace members (nothing
about `private` stops a workspace-internal deep import), so it gets the same
discipline as a published one; a private package torn out under
`tests/<basename>/` is a test harness with no importable surface at all, so it
stays exempt. Packages without TypeScript sources (config-only packages
shipping JSON) have no internals to seal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerberus.checks import story_docs, test_seam
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "lib-ts-tests"
SUMMARY = "libraries export only the root seam and their story tests reach workspace code only through fixture aliases"
SCOPE = Scope.CONTENT

_TS_SOURCE_SUFFIXES = (".ts", ".tsx")
_OK_MESSAGE = "every library exports only the root seam; story tests reach workspace code only through fixture aliases"


def _has_ts_sources(package: str, paths: list[str]) -> bool:
    prefix = f"{package}/" if package else ""
    return any(path.startswith(prefix) and path.endswith(_TS_SOURCE_SUFFIXES) for path in paths)


def _is_library(package: str, manifest: dict[str, Any]) -> bool:
    if manifest.get("bin"):
        return False
    if package.startswith("tests/"):
        return not manifest.get("private")
    return True


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    paths = ctx.paths(repo)
    members = story_docs.ts_member_dirs(repo, ctx, paths)
    if not members:
        res.skip("no TypeScript packages")
        return res

    seam = test_seam.Seam.from_paths(repo, ctx, "library", paths)
    libraries = [m for m in members if _has_ts_sources(m, paths) and _is_library(m, seam.load_manifest(m))]
    if not libraries:
        res.skip("no libraries")
        return res

    for package in sorted(libraries):
        seam.check_package(res, package)

    if not res.problems:
        res.ok(_OK_MESSAGE)
    return res
