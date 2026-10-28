from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cerberus import SourceKind, SourceScope, load_source_scope

if TYPE_CHECKING:
    from pathlib import Path

SCOPE_KEY = pytest.StashKey[SourceScope]()
__all__ = ["pytest_configure", "pytest_ignore_collect"]


def pytest_configure(config: pytest.Config) -> None:
    config.stash[SCOPE_KEY] = load_source_scope(config.rootpath)


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    if not collection_path.is_relative_to(config.rootpath):
        return None
    relative = collection_path.relative_to(config.rootpath).as_posix()
    scope = config.stash[SCOPE_KEY]
    if not collection_path.is_dir():
        return True if scope.classify(relative).kind is SourceKind.DEMO else None
    if scope.classify_directory(relative).kind is not SourceKind.DEMO:
        return None
    patterns = (*scope.production_roots, *scope.infrastructure_roots, *scope.tooling_roots, *scope.test_roots)
    retained = (
        path
        for pattern in patterns
        for path in config.rootpath.glob(pattern)
        if path.is_dir()
        and path.is_relative_to(collection_path)
        and scope.classify_directory(path.relative_to(config.rootpath).as_posix()).kind is not SourceKind.DEMO
    )
    if not any(retained):
        return True
    return None
