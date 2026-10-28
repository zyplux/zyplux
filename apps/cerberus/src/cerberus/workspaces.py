"""Workspace membership from the repo's own manifests — pnpm workspace globs
(pnpm-workspace.yaml `packages`) and uv `[tool.uv.workspace] members` in
pyproject.toml — for checks that scope an analysis to workspace-registered
code. Manifest decode errors propagate so each check can report them as its
own targeted finding.
"""

from __future__ import annotations

import tomllib
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from cerberus.context import Context
    from cerberus.model import Repo
    from cerberus.source_oracle import SourceOracle

_SUBTREE_SUFFIX = "/**"
RELEASE_AGE_MINUTES = 1440


def ts_member_globs(repo: Repo, ctx: Context) -> list[str]:
    manifest = ctx.file(repo, "pnpm-workspace.yaml")
    if manifest is None:
        return []
    data = yaml.safe_load(manifest)
    packages: list[Any] = data.get("packages", []) if isinstance(data, dict) else []
    return [glob for glob in packages if isinstance(glob, str)] if isinstance(packages, list) else []


def uv_member_globs(repo: Repo, ctx: Context) -> list[str]:
    pyproject = ctx.file(repo, "pyproject.toml")
    if pyproject is None:
        return []
    workspace = tomllib.loads(pyproject).get("tool", {}).get("uv", {}).get("workspace", {})
    return list(workspace.get("members", []))


def matches_globs(directory: str, globs: Iterable[str]) -> bool:
    """Match a dir against member globs the way a workspace manager does — `*` within a path segment, `**` any depth."""
    return any(PurePosixPath(directory).full_match(glob.rstrip("/")) for glob in globs)


def _excluded_globs(globs: Iterable[str]) -> list[str]:
    """The `!` patterns a manifest excludes; a trailing `/**` also names the dir itself, as pnpm reads it."""
    excluded = []
    for glob in globs:
        if not glob.startswith("!"):
            continue
        pattern = glob.removeprefix("!").rstrip("/")
        excluded.append(pattern)
        if pattern.endswith(_SUBTREE_SUFFIX):
            excluded.append(pattern[: -len(_SUBTREE_SUFFIX)])
    return excluded


def member_paths(root: Path, globs: Iterable[str]) -> list[Path]:
    """Every dir on disk that `globs` registers as a workspace member, `!` exclusions honoured."""
    included = [glob for glob in globs if not glob.startswith("!")]
    excluded = _excluded_globs(globs)
    matched = {match for glob in included for match in root.glob(glob) if match.is_dir()}
    return sorted(m for m in matched if not matches_globs(m.relative_to(root).as_posix(), excluded))


def member_dirs(paths: list[str], globs: list[str], manifest_name: str) -> list[str]:
    """Every dir carrying `manifest_name` that `globs` registers as a workspace member, `!` exclusions honoured."""
    suffix = f"/{manifest_name}"
    dirs = {path[: -len(suffix)] for path in paths if path.endswith(suffix)}
    included = [glob for glob in globs if not glob.startswith("!")]
    excluded = _excluded_globs(globs)
    return sorted(d for d in dirs if matches_globs(d, included) and not matches_globs(d, excluded))


def ts_member_dirs(repo: Repo, ctx: Context, paths: list[str]) -> list[str]:
    """Every JS/TS workspace member dir — the test-harness members included."""
    if ctx.file(repo, "package.json") is None:
        return []
    globs = ts_member_globs(repo, ctx)
    if globs:
        return member_dirs(paths, globs, "package.json")
    return [""]


def list_source_members(dirs: list[str], source: SourceOracle) -> list[str]:
    return [directory for directory in dirs if not source.classify_directory(directory).is_test]
