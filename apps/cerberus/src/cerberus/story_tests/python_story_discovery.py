"""Find testable Python packages and their story test files."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerberus.story_tests.story_source_discovery import PY_TEST, has_story_marker
from cerberus.syntax.toml_tables import parse_toml
from cerberus.workspaces.workspace_members import member_dirs

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo


def load_package_manifest(repo: Repo, ctx: Context, package: str) -> dict[str, Any]:
    path = f"{package}/pyproject.toml" if package else "pyproject.toml"
    return parse_toml(ctx.file(repo, path)) or {}


def is_under_package(path: str, package: str) -> bool:
    """Match package-local files and the corresponding top-level tests directory."""
    basename = package.rsplit("/", 1)[-1]
    return not package or path.startswith((f"{package}/", f"tests/{basename}/"))


def list_testable_python_packages(repo: Repo, ctx: Context, paths: list[str]) -> list[str]:
    manifest = load_package_manifest(repo, ctx, "")
    tool = manifest.get("tool")
    uv = tool.get("uv") if isinstance(tool, dict) else None
    workspace = uv.get("workspace") if isinstance(uv, dict) else None
    if isinstance(workspace, dict):
        members = [glob for glob in workspace.get("members", []) if isinstance(glob, str)]
        packages = member_dirs(paths, members, "pyproject.toml")
    else:
        packages = [""] if isinstance(manifest.get("project"), dict) else []
    return [package for package in packages if ctx.config.source_oracle.classify_directory(package).needs_tests]


def list_python_story_tests(repo: Repo, ctx: Context, package: str, paths: list[str]) -> list[str]:
    return [
        path
        for path in paths
        if is_under_package(path, package)
        and PY_TEST.fullmatch(path.rsplit("/", 1)[-1])
        and has_story_marker(ctx.file(repo, path) or "")
    ]
