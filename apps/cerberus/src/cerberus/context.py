from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cerberus.config import Config
from cerberus.model import Repo
from cerberus.source import GitHubSource, LocalSource, RepoSource


@dataclass
class Context:
    config: Config
    source: RepoSource
    fix: bool = False
    _cache: dict[Any, Any] = field(default_factory=dict)

    @property
    def org(self) -> str:
        return self.config.org

    def _cached(self, key: Any, producer: Callable[[], Any]) -> Any:
        if key not in self._cache:
            self._cache[key] = producer()
        return self._cache[key]

    def repos(self) -> list[Repo]:
        return self._cached("repos", self.source.repos)

    def file(self, repo: Repo, path: str) -> str | None:
        return self._cached(("file", repo.name, path), lambda: self.source.file(repo, path))

    def paths(self, repo: Repo) -> list[str]:
        return self._cached(("paths", repo.name), lambda: self.source.list_paths(repo))

    def tags(self, repo: Repo, prefix: str) -> list[str]:
        return self._cached(("tags", repo.name, prefix), lambda: self.source.tags(repo, prefix))

    def changed_paths(self, repo: Repo, ref: str, surface: Sequence[str]) -> list[str]:
        key = ("changed_paths", repo.name, ref, tuple(surface))
        return self._cached(key, lambda: self.source.changed_paths(repo, ref, surface))

    def write_file(self, repo: Repo, path: str, content: str) -> None:
        self.source.write_file(repo, path, content)
        self._cache[("file", repo.name, path)] = content

    def workflows(self, repo: Repo) -> dict[str, str]:
        return self._cached(("workflows", repo.name), lambda: self.source.workflows(repo))

    def repo_secrets(self, repo: Repo) -> set[str]:
        return self._cached(("repo_secrets", repo.name), lambda: self.source.repo_secrets(repo))

    def _org_secrets(self) -> dict[str, str]:
        return self._cached("org_secrets", self.source.org_secrets)

    def _org_secret_selected_repos(self, name: str) -> set[str]:
        return self._cached(
            ("org_secret_repos", name), lambda: self.source.org_secret_selected_repos(name)
        )

    def secret_available(self, repo: Repo, name: str) -> bool:
        if name in self.repo_secrets(repo):
            return True
        visibility = self._org_secrets().get(name)
        if visibility is None:
            return False
        if visibility == "all":
            return True
        if visibility == "private":
            return repo.is_private
        if visibility == "selected":
            return repo.name in self._org_secret_selected_repos(name)
        return False


def github_context(config: Config) -> Context:
    return Context(config=config, source=GitHubSource(config))


def local_context(config: Config, root: Path, fix: bool = False) -> Context:
    return Context(config=config, source=LocalSource(root), fix=fix)
