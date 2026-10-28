from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath


class SourceKind(StrEnum):
    PRODUCT = "product"
    INFRASTRUCTURE = "infrastructure"
    TOOLING = "tooling"
    DEMO = "demo"
    TESTS = "tests"


@dataclass(frozen=True)
class SourceClassification:
    kind: SourceKind
    root: str
    is_test: bool
    requires_tests: bool


@dataclass(frozen=True)
class SourceScope:
    """Classify repository-relative file paths without reading the filesystem."""

    production_roots: tuple[str, ...]
    test_files: tuple[str, ...]
    infrastructure_roots: tuple[str, ...] = ()
    tooling_roots: tuple[str, ...] = ()
    demo_roots: tuple[str, ...] = ()
    test_roots: tuple[str, ...] = ()
    test_exempt_files: tuple[str, ...] = ()

    def classify(self, path: str) -> SourceClassification:
        target = PurePosixPath(path)
        groups = (
            (SourceKind.PRODUCT, self.production_roots),
            (SourceKind.INFRASTRUCTURE, self.infrastructure_roots),
            (SourceKind.TOOLING, self.tooling_roots),
            (SourceKind.DEMO, self.demo_roots),
            (SourceKind.TESTS, self.test_roots),
        )
        matches = [
            (len(parent.parts), len(pattern.replace("*", "").replace("?", "")), str(parent), kind)
            for parent in target.parents
            for kind, patterns in groups
            for pattern in patterns
            if parent.full_match(pattern.rstrip("/"))
        ]
        root, kind = ".", SourceKind.TOOLING
        if matches:
            priority = max(match[:2] for match in matches)
            owners = {(root, kind) for depth, specificity, root, kind in matches if (depth, specificity) == priority}
            if len(owners) != 1:
                message = (
                    f"[source] assigns conflicting owners to {path}: {', '.join(sorted(kind for _, kind in owners))}"
                )
                raise ValueError(message)
            root, kind = owners.pop()
        is_test = kind is SourceKind.TESTS or any(target.full_match(pattern) for pattern in self.test_files)
        requires_tests = (
            not is_test
            and kind is not SourceKind.DEMO
            and not any(target.full_match(pattern) for pattern in self.test_exempt_files)
        )
        return SourceClassification(kind, root, is_test, requires_tests)

    def is_test_file(self, path: str) -> bool:
        return self.classify(path).is_test

    def classify_directory(self, directory: str) -> SourceClassification:
        return self.classify((PurePosixPath(directory) / "_").as_posix())

    def find_production_root(self, path: str) -> str | None:
        classification = self.classify(path)
        return classification.root if classification.kind is SourceKind.PRODUCT and not classification.is_test else None

    def is_production_file(self, path: str) -> bool:
        return self.find_production_root(path) is not None
