from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class SourceScope:
    """Classify repository-relative file paths without reading the filesystem."""

    production_roots: tuple[str, ...]
    test_files: tuple[str, ...]

    def is_test_file(self, path: str) -> bool:
        return any(PurePosixPath(path).full_match(pattern) for pattern in self.test_files)

    def find_production_root(self, path: str) -> str | None:
        if self.is_test_file(path):
            return None
        return next(
            (
                str(parent)
                for parent in PurePosixPath(path).parents
                if any(parent.full_match(pattern.rstrip("/")) for pattern in self.production_roots)
            ),
            None,
        )

    def is_production_file(self, path: str) -> bool:
        return self.find_production_root(path) is not None
