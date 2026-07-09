"""Freshness guard for the npm tool versions pinned in `cerberus.tool_pins`:
compares each pin against npm's `dist-tags.latest` so a frozen pin cannot rot
unnoticed. The check bites only in the repo that carries the pin source —
that is the one place the fix (bump the pin, dogfood it through the gate,
release cerberus) can happen; consumer repos get the new pins through
`zyplux_deps_latest` forcing them onto the latest cerberus, so they skip.
A failed lookup is reported as an error, never a silent pass, and there is
no `--fix`: a tool version change under the gate deserves a human eye.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus import registries, tool_pins
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "tool_pins_latest"
SUMMARY = "the npm tool versions pinned in cerberus source are the latest npm releases"
SCOPE = Scope.CONTENT

_PIN_SOURCE_SUFFIX = "src/cerberus/tool_pins.py"


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    pin_source = next((path for path in ctx.paths(repo) if path.endswith(_PIN_SOURCE_SUFFIX)), None)
    if pin_source is None:
        res.skip("no cerberus tool pins source in the repo")
        return res
    for tool, pinned in sorted(tool_pins.NPM_TOOL_PINS.items()):
        try:
            latest = registries.fetch_latest_npm(tool)
        except registries.RegistryLookupError as err:
            res.error(f"could not determine the latest `{tool}`: {err}")
            continue
        if pinned != latest:
            res.fail(
                f"`{tool}` is pinned {pinned} in {pin_source}, npm latest is {latest};"
                " bump the pin and release cerberus"
            )
    if not res.problems:
        res.ok("every pinned npm tool is at its latest release")
    return res
