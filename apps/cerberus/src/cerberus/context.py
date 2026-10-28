from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from cerberus.source import LocalSource, RepoSource

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from cerberus.config import Config
    from cerberus.model import Repo


@dataclass
class Context:
    config: Config
    source: RepoSource
    fix: bool = False
    verbose: bool = False
    config_path: Path | None = None
    _cache: dict[object, Any] = field(default_factory=dict)

    def _cached[T](self, key: object, producer: Callable[[], T]) -> T:
        if key not in self._cache:
            self._cache[key] = producer()
        return self._cache[key]

    def repos(self) -> list[Repo]:
        return self._cached("repos", self.source.repos)

    def file(self, repo: Repo, path: str) -> str | None:
        return self._cached(("file", repo.name, path), lambda: self.source.file(repo, path))

    def paths(self, repo: Repo) -> list[str]:
        return self._cached(("paths", repo.name), lambda: self.source.list_paths(repo))

    def file_at_ref(self, repo: Repo, ref: str, path: str) -> str | None:
        key = ("file_at_ref", repo.name, ref, path)
        return self._cached(key, lambda: self.source.file_at_ref(repo, ref, path))

    def write_file(self, repo: Repo, path: str, content: str) -> None:
        self.source.write_file(repo, path, content)
        self._cache["file", repo.name, path] = content

    def workflows(self, repo: Repo) -> dict[str, str]:
        return self._cached(("workflows", repo.name), lambda: self.source.workflows(repo))


def local_context(
    config: Config, root: Path, *, fix: bool = False, verbose: bool = False, config_path: Path | None = None
) -> Context:
    return Context(config=config, source=LocalSource(root), fix=fix, verbose=verbose, config_path=config_path)
