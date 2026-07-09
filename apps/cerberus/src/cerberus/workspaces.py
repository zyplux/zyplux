"""Workspace membership from the repo's own manifests — bun `workspaces`
globs in package.json and uv `[tool.uv.workspace] members` in pyproject.toml —
for checks that scope an analysis to workspace-registered code. Manifest
decode errors propagate so each check can report them as its own targeted
finding.
"""

from __future__ import annotations

import json
import tomllib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo


def bun_member_globs(repo: Repo, ctx: Context) -> list[str]:
    package_json = ctx.file(repo, "package.json")
    if package_json is None:
        return []
    registered = json.loads(package_json).get("workspaces", [])
    if isinstance(registered, dict):
        registered = registered.get("packages", [])
    return list(registered)


def uv_member_globs(repo: Repo, ctx: Context) -> list[str]:
    pyproject = ctx.file(repo, "pyproject.toml")
    if pyproject is None:
        return []
    workspace = tomllib.loads(pyproject).get("tool", {}).get("uv", {}).get("workspace", {})
    return list(workspace.get("members", []))
