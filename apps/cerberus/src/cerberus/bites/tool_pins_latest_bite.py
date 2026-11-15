"""Check the source pins against npm releases eligible under the pnpm quarantine."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from airlock import registries
from airlock.errors import RELEASE_ERRORS

from cerberus.model import CheckResult, Scope
from cerberus.toolchain import pnpm_policy

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "tool_pins_latest"
SUMMARY = "the npm tool versions pinned in cerberus source are the newest quarantine-eligible releases"
SCOPE = Scope.CONTENT

_PIN_SOURCE_SUFFIX = "src/cerberus/toolchain/pnpm_policy.py"


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    pin_source = next((path for path in ctx.paths(repo) if path.endswith(_PIN_SOURCE_SUFFIX)), None)
    if pin_source is None:
        res.skip("no cerberus tool pins source in the repo")
        return res
    for tool, pinned in sorted(pnpm_policy.NPM_TOOL_PINS.items()):
        try:
            latest = registries.fetch_latest_npm(tool, minimum_age=timedelta(minutes=pnpm_policy.RELEASE_AGE_MINUTES))
        except RELEASE_ERRORS as err:
            res.error(f"could not determine the latest `{tool}`: {err}")
            continue
        if pinned != latest:
            res.fail(
                f"`{tool}` is pinned {pinned} in {pin_source}, newest quarantine-eligible release is {latest};"
                " bump the pin and release cerberus"
            )
    if not res.problems:
        res.ok("every pinned npm tool is at its newest quarantine-eligible release")
    return res
