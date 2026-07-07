from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

_TS_SUFFIXES = (".ts", ".tsx")
_DEFAULT_ENTRY = "src/index.ts"
_EXPORT_TARGET_KEYS = ("import", "default", "types")


@dataclass(frozen=True)
class PackageInfo:
    directory: str
    manifest: dict[str, Any]


def build_package_index(paths: list[str], read: Callable[[str], str | None]) -> dict[str, PackageInfo]:
    index: dict[str, PackageInfo] = {}
    for path in paths:
        if "node_modules/" in path or not (path == "package.json" or path.endswith("/package.json")):
            continue
        content = read(path)
        if content is None:
            continue
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        name = data.get("name")
        if isinstance(name, str):
            directory = path.rsplit("/", 1)[0] if "/" in path else ""
            index[name] = PackageInfo(directory, data)
    return index


def _entry_from_exports(exports: object) -> str | None:
    if isinstance(exports, str):
        return exports
    if not isinstance(exports, dict):
        return None
    target = exports.get(".")
    if isinstance(target, str):
        return target
    if isinstance(target, dict):
        for key in _EXPORT_TARGET_KEYS:
            value = target.get(key)
            if isinstance(value, str):
                return value
    return None


def _entry_point(manifest: dict[str, Any]) -> str:
    main = manifest.get("main")
    return _entry_from_exports(manifest.get("exports")) or (main if isinstance(main, str) else None) or _DEFAULT_ENTRY


def _resolve_relative(file_path: str, specifier: str, known_files: frozenset[str]) -> str | None:
    base = posixpath.normpath(posixpath.join(posixpath.dirname(file_path), specifier))
    candidates = [f"{base}{suffix}" for suffix in _TS_SUFFIXES]
    candidates += [f"{base}/index{suffix}" for suffix in _TS_SUFFIXES]
    return next((candidate for candidate in candidates if candidate in known_files), None)


def _resolve_alias(specifier: str, package_index: dict[str, PackageInfo], known_files: frozenset[str]) -> str | None:
    info = package_index.get(specifier)
    if info is None:
        return None
    entry = _entry_point(info.manifest).removeprefix("./")
    candidate = posixpath.normpath(f"{info.directory}/{entry}") if info.directory else entry
    return candidate if candidate in known_files else None


def resolve(file_path: str, specifier: str, known_files: frozenset[str], package_index: dict[str, PackageInfo]) -> str | None:
    if specifier.startswith(("./", "../")):
        return _resolve_relative(file_path, specifier, known_files)
    return _resolve_alias(specifier, package_index, known_files)
