"""Parse TOML for checks that report malformed configuration as findings."""

from __future__ import annotations

import tomllib
from typing import Any


def parse_toml(content: str | None) -> dict[str, Any] | None:
    if content is None:
        return None
    try:
        return tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return None
