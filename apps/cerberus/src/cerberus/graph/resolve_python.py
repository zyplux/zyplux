from __future__ import annotations

import posixpath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cerberus.graph.parse import PyImportRef

_INIT_PY = "__init__.py"


def _join(directory: str, tail: str) -> str:
    return f"{directory}/{tail}" if directory else tail


def _ancestor(directory: str, levels_up: int) -> str | None:
    current = directory
    for _ in range(levels_up):
        if not current:
            return None
        current = posixpath.dirname(current)
    return current


def _module_stem(path: str) -> str | None:
    if path.endswith(f"/{_INIT_PY}"):
        return path[: -len(f"/{_INIT_PY}")]
    if path.endswith(".py"):
        return path[: -len(".py")]
    return None


def _matches_absolute(path: str, slash: str) -> bool:
    stem = _module_stem(path)
    return stem is not None and (stem == slash or stem.endswith(f"/{slash}"))


def _resolve_absolute(dotted: str, known_files: frozenset[str]) -> str | None:
    slash = dotted.replace(".", "/")
    matches = [path for path in known_files if _matches_absolute(path, slash)]
    return min(matches, key=len) if matches else None


def _resolve_relative(file_path: str, level: int, dotted: str, known_files: frozenset[str]) -> str | None:
    base = _ancestor(posixpath.dirname(file_path), level - 1)
    if base is None:
        return None
    slash = dotted.replace(".", "/")
    module_file = _join(base, f"{slash}.py")
    package_file = _join(base, f"{slash}/{_INIT_PY}")
    if module_file in known_files:
        return module_file
    if package_file in known_files:
        return package_file
    return None


def resolve(file_path: str, ref: PyImportRef, known_files: frozenset[str]) -> str | None:
    if ref.level == 0:
        return _resolve_absolute(ref.dotted, known_files)
    return _resolve_relative(file_path, ref.level, ref.dotted, known_files)
