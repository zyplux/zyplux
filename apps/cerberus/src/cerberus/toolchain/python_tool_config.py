"""Shared machinery for checks on Python tool configs (ruff, pyrefly, pytest).

Each of those checks starts the same way: the repo counts as Python only when
a root `pyproject.toml` exists, and the org keeps lint/type tool config in a
standalone `<tool>.toml` — never embedded under `[tool.<name>]` in
`pyproject.toml`.
"""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo

PYPROJECT = "pyproject.toml"


def parse_toml(content: str) -> dict[str, Any] | None:
    try:
        parsed = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else {}


def load_pyproject(repo: Repo, ctx: Context, res: CheckResult, *, standalone_tool: str | None = None) -> str | None:
    """Read pyproject.toml and reject embedded settings for a standalone tool."""
    content = ctx.file(repo, PYPROJECT)
    if content is None:
        res.skip(f"no {PYPROJECT} (not a Python repo)")
        return None
    if standalone_tool is not None:
        config = parse_toml(content) or {}
        tables = config.get("tool")
        if isinstance(tables, dict) and standalone_tool in tables:
            res.fail(f"{standalone_tool} config lives in {PYPROJECT}; move it to a standalone {standalone_tool}.toml")
            return None
    return content
