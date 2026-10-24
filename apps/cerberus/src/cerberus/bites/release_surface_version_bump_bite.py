from __future__ import annotations

from typing import TYPE_CHECKING

from airlock import check_release_surface

from cerberus.model import CheckResult, Finding, Scope, Status

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "release_surface_version_bump"
SUMMARY = "a published target's version is bumped by exactly one step whenever its release surface changes"
SCOPE = Scope.GIT_HISTORY


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    if ctx.file(repo, "airlock-targets.toml") is None:
        res.skip("no airlock-targets.toml — repo publishes nothing")
        return res
    res.findings.extend(
        Finding(Status[finding.status.upper()], finding.message)
        for finding in check_release_surface(root=ctx.source.root)
    )
    return res
