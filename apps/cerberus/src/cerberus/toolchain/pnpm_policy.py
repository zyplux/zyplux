"""Define pnpm's release quarantine and the exact versions of tools run through pnpx."""

from __future__ import annotations

RELEASE_AGE_MINUTES = 1440

NPM_TOOL_PINS: dict[str, str] = {
    "jscpd": "5.4.3",
    "fallow": "3.43.0",
}


def format_spec(tool: str) -> str:
    return f"{tool}@{NPM_TOOL_PINS[tool]}"
