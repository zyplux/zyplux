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
    # Descend into directories so a more specific owner can retain its nested tests.
    if collection_path.is_dir() or not collection_path.is_relative_to(config.rootpath):
        return None
    relative = collection_path.relative_to(config.rootpath).as_posix()
    if config.stash[SCOPE_KEY].classify(relative).kind is SourceKind.DEMO:
        return True
    return None
