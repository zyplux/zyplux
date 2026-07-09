"""Shared machinery for checks on Python tool configs (ruff, pyrefly, pytest_coverage_floor).

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


def load_pyproject(repo: Repo, ctx: Context, res: CheckResult) -> str | None:
    """The root pyproject.toml's content; records a skip and returns None for a non-Python repo."""
    content = ctx.file(repo, PYPROJECT)
    if content is None:
        res.skip(f"no {PYPROJECT} (not a Python repo)")
    return content


def fail_when_embedded(pyproject: str, tool_name: str, res: CheckResult) -> bool:
    """Whether pyproject.toml embeds `[tool.<name>]`; records the standalone-config failure when it does."""
    config = parse_toml(pyproject) or {}
    tables = config.get("tool")
    if isinstance(tables, dict) and tool_name in tables:
        res.fail(f"{tool_name} config lives in {PYPROJECT}; move it to a standalone {tool_name}.toml")
        return True
    return False
