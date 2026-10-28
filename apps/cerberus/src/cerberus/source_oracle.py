from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from pathlib import PurePosixPath


class SourceKind(StrEnum):
    PROD = "prod"
    INFRA = "infra"
    DEMO = "demo"
    TEST = "test"
    DOCS = "docs"


@dataclass(frozen=True)
class SourceType:
    roots: tuple[str, ...]
    needs_tests: bool
    allowed_child_types: frozenset[SourceKind]


@dataclass(frozen=True)
class SourceClassification:
    kind: SourceKind
    root: str
    is_test: bool
    needs_tests: bool


@dataclass(frozen=True)
class SourceOracle:
    """Classify repository-relative paths without reading the filesystem."""

    types: dict[SourceKind, SourceType]
    default_type: SourceKind
    test_files: tuple[str, ...]
    test_exempt_files: tuple[str, ...]

    def _find_type(self, directory: PurePosixPath) -> SourceKind | None:
        matches = [
            (len(pattern.replace("*", "").replace("?", "")), kind)
            for kind, source_type in self.types.items()
            for pattern in source_type.roots
            if directory.full_match(pattern.rstrip("/"))
        ]
        if not matches:
            return None
        specificity = max(rank for rank, _ in matches)
        kinds = {kind for rank, kind in matches if rank == specificity}
        if len(kinds) != 1:
            message = f"[source_oracle] assigns conflicting categories to {directory}: {', '.join(sorted(kinds))}"
            raise ValueError(message)
        return kinds.pop()

    def classify(self, path: str) -> SourceClassification:
        target = PurePosixPath(path)
        scopes = [
            (str(parent), kind)
            for parent in reversed((target, *target.parents))
            if (kind := self._find_type(parent)) is not None
        ]
        for (parent, parent_kind), (child, child_kind) in pairwise(scopes):
            if parent_kind != child_kind and child_kind not in self.types[parent_kind].allowed_child_types:
                message = f"[source_oracle] {parent_kind} scope {parent} cannot contain {child_kind} scope {child}"
                raise ValueError(message)
        root, kind = scopes[-1] if scopes else (".", self.default_type)
        is_test = kind is SourceKind.TEST or any(target.full_match(pattern) for pattern in self.test_files)
        needs_tests = (
            self.types[kind].needs_tests
            and not is_test
            and not any(target.full_match(pattern) for pattern in self.test_exempt_files)
        )
        return SourceClassification(kind, root, is_test, needs_tests)

    def is_test_file(self, path: str) -> bool:
        return self.classify(path).is_test

    def classify_directory(self, directory: str) -> SourceClassification:
        return self.classify((PurePosixPath(directory) / "_").as_posix())

    def find_production_root(self, path: str) -> str | None:
        classification = self.classify(path)
        return classification.root if classification.kind is SourceKind.PROD and not classification.is_test else None

    def is_production_file(self, path: str) -> bool:
        return self.find_production_root(path) is not None
