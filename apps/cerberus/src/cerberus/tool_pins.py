"""Exact versions of the npm tools cerberus runs via `bunx`.

The pins live in source rather than `cerberus.toml` so no repo overlay can
drift a tool version away from the org: every cerberus release carries them
frozen, and consumers get a new tool version only through a new release.
The `tool_pins_latest` bite compares these pins against npm's latest in the
repo that carries this file, so a lagging pin fails that repo's gate — the
fix is bumping the pin here and releasing cerberus.
"""

from __future__ import annotations

NPM_TOOL_PINS: dict[str, str] = {
    "jscpd": "5.0.12",
    "fallow": "3.3.0",
}


def format_spec(tool: str) -> str:
    return f"{tool}@{NPM_TOOL_PINS[tool]}"
