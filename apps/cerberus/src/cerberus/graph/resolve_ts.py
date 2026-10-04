from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

_TS_SUFFIXES = (".ts", ".tsx")
_EXPORT_TARGET_KEYS = {"import", "default"}


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


def select_target(exports: object, key: str = ".") -> str | None:
    if not isinstance(exports, (dict, list)):
        return exports if isinstance(exports, str) else None
    if isinstance(exports, list):
        return next((target for entry in exports if (target := select_target(entry, key)) is not None), None)
    if any(name.startswith(".") for name in exports):
        if key in exports:
            return select_target(exports[key])
        return _pattern_target(exports, key)
    for condition, entry in exports.items():
        if condition in _EXPORT_TARGET_KEYS:
            return select_target(entry)

    return None


def _pattern_target(exports: dict[str, Any], key: str) -> str | None:
    for pattern in sorted(exports, key=len, reverse=True):
        if "*" not in pattern:
            continue
        prefix, suffix = pattern.split("*", 1)
        if key.startswith(prefix) and key.endswith(suffix):
            match = key[len(prefix) : len(key) - len(suffix) if suffix else None]
            target = select_target(exports[pattern])
            return target.replace("*", match) if target is not None else None
    return None


def _resolve_relative(file_path: str, specifier: str, known_files: frozenset[str]) -> str | None:
    base = posixpath.normpath(posixpath.join(posixpath.dirname(file_path), specifier))
    candidates = [base]
    if base.endswith((".js", ".mjs")):
        candidates += [base.rsplit(".", 1)[0] + suffix for suffix in _TS_SUFFIXES]
    candidates += [f"{base}{suffix}" for suffix in _TS_SUFFIXES]
    candidates += [f"{base}/index{suffix}" for suffix in _TS_SUFFIXES]
    return next((candidate for candidate in candidates if candidate in known_files), None)


def _resolve_alias(specifier: str, package_index: dict[str, PackageInfo], known_files: frozenset[str]) -> str | None:
    name = next((name for name in package_index if specifier == name or specifier.startswith(f"{name}/")), None)
    info = package_index.get(name) if name is not None else None
    if info is None:
        return None
    key = "." + specifier[len(name) :] if name is not None else "."
    entry = select_target(info.manifest.get("exports"), key)
    if entry is None and "exports" not in info.manifest:
        entry = info.manifest.get("main", "src/index.ts") if key == "." else key
    if not isinstance(entry, str):
        return None
    return _resolve_relative(posixpath.join(info.directory, "package.json"), entry, known_files)


def resolve(
    file_path: str, specifier: str, known_files: frozenset[str], package_index: dict[str, PackageInfo]
) -> str | None:
    if specifier.startswith(("./", "../")):
        return _resolve_relative(file_path, specifier, known_files)
    if specifier.startswith("#"):
        owners = sorted(
            (
                info
                for info in package_index.values()
                if (not info.directory or file_path.startswith(f"{info.directory}/"))
            ),
            key=lambda info: len(info.directory),
            reverse=True,
        )
        if owners:
            imports = owners[0].manifest.get("imports", {})
            target = select_target({f".{key}": value for key, value in imports.items()}, f".{specifier}")
            if target is not None:
                return _resolve_relative(posixpath.join(owners[0].directory, "package.json"), target, known_files)
    return _resolve_alias(specifier, package_index, known_files)
