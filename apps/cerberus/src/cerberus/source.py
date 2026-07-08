from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from cerberus import proc
from cerberus.model import Repo

if TYPE_CHECKING:
    from collections.abc import Sequence


class GitHistoryUnavailableError(RuntimeError):
    """Git history (tags, ref diffs) could not be read — git failed or is absent."""


class RepoSource(Protocol):
    """Where a check reads a repo's facts from: a local checkout."""

    root: Path

    def repos(self) -> list[Repo]: ...
    def file(self, _repo: Repo, path: str) -> str | None: ...
    def list_paths(self, _repo: Repo) -> list[str]: ...
    def changed_paths(self, _repo: Repo, ref: str, surface: Sequence[str]) -> list[str]: ...
    def write_file(self, _repo: Repo, path: str, content: str) -> None: ...
    def workflows(self, _repo: Repo) -> dict[str, str]: ...


class LocalSource:
    """Reads a single repo from a working-tree checkout on disk."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def repos(self) -> list[Repo]:
        slug = os.environ.get("GITHUB_REPOSITORY", "")
        name = slug.split("/", 1)[1] if "/" in slug else self.root.resolve().name
        return [Repo(name=name)]

    def file(self, _repo: Repo, path: str) -> str | None:
        try:
            return (self.root / path).read_text()
        except OSError:
            return None

    def list_paths(self, _repo: Repo) -> list[str]:
        tracked = self._git_tracked()
        return tracked if tracked is not None else self._walk_files()

    def _git_tracked(self) -> list[str] | None:
        """Tracked file paths via git — mirrors the GitHub tree (honours .gitignore)."""
        try:
            result = proc.run(["git", "-C", str(self.root), "ls-files", "-z"])
        except proc.ToolNotFoundError:
            return None
        if result.returncode != 0:
            return None
        return sorted(path for path in result.stdout.split("\0") if path)

    def _git(self, args: list[str]) -> str:
        try:
            result = proc.run(["git", "-C", str(self.root), *args])
        except proc.ToolNotFoundError as exc:
            raise GitHistoryUnavailableError(str(exc)) from exc
        if result.returncode != 0:
            raise GitHistoryUnavailableError(result.stderr.strip() or f"git {args[0]} failed")
        return result.stdout

    def changed_paths(self, _repo: Repo, ref: str, surface: Sequence[str]) -> list[str]:
        """Diffs `ref` against the working tree, so uncommitted local changes count too."""
        diff = self._git(["diff", "--name-only", ref, "--", *surface])
        return [path for path in diff.splitlines() if path]

    def _walk_files(self) -> list[str]:
        skip = {"node_modules", ".git", ".venv", "dist", ".output", "__pycache__"}
        out: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [name for name in dirnames if name not in skip]
            base = Path(dirpath)
            out.extend((base / name).relative_to(self.root).as_posix() for name in filenames)
        return sorted(out)

    def write_file(self, _repo: Repo, path: str, content: str) -> None:
        (self.root / path).write_text(content)

    def workflows(self, _repo: Repo) -> dict[str, str]:
        workflow_dir = self.root / ".github" / "workflows"
        if not workflow_dir.is_dir():
            return {}
        out: dict[str, str] = {}
        for entry in sorted(workflow_dir.iterdir()):
            if entry.is_file() and entry.suffix in {".yml", ".yaml"}:
                try:
                    out[entry.name] = entry.read_text()
                except OSError:
                    continue
        return out
