"""Load project metadata and check that Python tool settings are standalone."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.syntax.toml_tables import parse_toml

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo

PYPROJECT = "pyproject.toml"


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
