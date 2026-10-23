from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from cerberus import workspaces
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "pnpm_release_age"
SUMMARY = "pnpm workspaces quarantine new releases for one day, except @zyplux packages"
SCOPE = Scope.CONTENT

_OWN_PACKAGE_PREFIX = "@zyplux/"


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    content = ctx.file(repo, "pnpm-workspace.yaml")
    if content is None:
        res.skip("not a pnpm workspace")
        return res

    try:
        workspace = yaml.safe_load(content)
    except yaml.YAMLError:
        res.error("pnpm-workspace.yaml is not valid YAML")
        return res

    workspace: dict[object, object] = workspace if isinstance(workspace, dict) else {}
    if workspace.get("minimumReleaseAge") != workspaces.RELEASE_AGE_MINUTES:
        res.fail(f"minimumReleaseAge must be {workspaces.RELEASE_AGE_MINUTES} minutes")
    if workspace.get("minimumReleaseAgeExcludePrune") is not True:
        res.fail("minimumReleaseAgeExcludePrune must be true")

    exclusions = workspace.get("minimumReleaseAgeExclude", [])
    if not isinstance(exclusions, list) or not all(isinstance(package, str) for package in exclusions):
        res.fail("minimumReleaseAgeExclude must be a list of package selectors")
    else:
        external_packages = sorted(package for package in exclusions if not package.startswith(_OWN_PACKAGE_PREFIX))
        if external_packages:
            res.fail("minimumReleaseAgeExclude permits only @zyplux/* packages: " + ", ".join(external_packages))

    if not res.problems:
        res.ok("pnpm release-age policy is enforced")
    return res
