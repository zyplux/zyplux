"""Shared machinery for the `cli_ts_test_seam`/`lib_ts_test_seam` bites.

A public TypeScript package exposes the root export plus at most one extra
seam: `./contracts`, which must map to `./src/contracts.ts` (the schemas
describing the package's file and wire formats). Three facts enforce that
together, whatever the package type: the package's `exports` map exposes
nothing beyond those seams, its user-story tests reach workspace code only
through `#` fixture aliases (third-party modules and node builtins are fair
game — they cannot touch package internals), and the governing test
package's `imports` aliases stay inside the package so an alias cannot
tunnel back into package internals.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cerberus.bites import story_docs

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo

_CONTRACTS_EXPORT_KEY = "./contracts"
_CONTRACTS_TARGET = "./src/contracts.ts"
_SEAM_EXPORT_KEYS = frozenset({".", "./package.json", _CONTRACTS_EXPORT_KEY})
_SEAM_SPECIFIER_PREFIXES = ("#", "node:")
_PATH_SPECIFIER_PREFIXES = (".", "/")
_STORY_TEST_PATH = re.compile(r"(?:^|/)stories/[^/]+\.test\.tsx?$")
_STATIC_IMPORT = re.compile(r"^(?:import|export)\b[^;]*?\bfrom\s+'([^']+)'", re.MULTILINE | re.DOTALL)
_SIDE_EFFECT_IMPORT = re.compile(r"^import\s+'([^']+)'", re.MULTILINE)


def _parse_manifest(content: str | None) -> dict[str, Any]:
    if content is None:
        return {}
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _manifest_path(package: str) -> str:
    return f"{package}/package.json" if package else "package.json"


def _import_specifiers(content: str) -> list[str]:
    return [*_STATIC_IMPORT.findall(content), *_SIDE_EFFECT_IMPORT.findall(content)]


def _alias_targets(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [target for nested in value.values() for target in _alias_targets(nested)]
    return []


def _check_exports_surface(res: CheckResult, manifest_path: str, manifest: dict[str, Any], subject: str) -> None:
    exports = manifest.get("exports")
    if exports is None:
        res.fail(f"{manifest_path}: {subject} must declare exports; without one every internal module is importable")
        return
    if not isinstance(exports, dict):
        return
    subpaths = {key for key in exports if key.startswith(".")}
    if not subpaths:
        return
    if "." not in subpaths:
        res.fail(f"{manifest_path}: {subject} exports must include the '.' root seam")
    for key in sorted(subpaths - _SEAM_EXPORT_KEYS):
        res.fail(f"{manifest_path}: {subject} exports expose more than the root seam — {key!r}")
    if _CONTRACTS_EXPORT_KEY not in subpaths:
        return
    targets = _alias_targets(exports[_CONTRACTS_EXPORT_KEY])
    if not targets or any(target != _CONTRACTS_TARGET for target in targets):
        res.fail(f"{manifest_path}: {subject} '{_CONTRACTS_EXPORT_KEY}' seam must map to '{_CONTRACTS_TARGET}'")


def _governing_manifest(story_file: str, path_set: frozenset[str]) -> str | None:
    directory = story_file.rsplit("/", 1)[0]
    while "/" in directory:
        directory = directory.rsplit("/", 1)[0]
        candidate = f"{directory}/package.json"
        if candidate in path_set:
            return candidate
    return "package.json" if "package.json" in path_set else None


@dataclass(frozen=True)
class Seam:
    repo: Repo
    ctx: Context
    subject: str
    story_files: list[str]
    path_set: frozenset[str]
    workspace_names: frozenset[str]

    @classmethod
    def from_paths(cls, repo: Repo, ctx: Context, subject: str, paths: list[str]) -> Seam:
        story_files = [path for path in paths if _STORY_TEST_PATH.search(path)]
        members = story_docs.ts_member_dirs(repo, ctx, paths)
        names = frozenset(
            name
            for member in members
            if isinstance(name := _parse_manifest(ctx.file(repo, _manifest_path(member))).get("name"), str)
        )
        return cls(repo, ctx, subject, story_files, frozenset(paths), names)

    def load_manifest(self, package: str) -> dict[str, Any]:
        return _parse_manifest(self.ctx.file(self.repo, _manifest_path(package)))

    def check_package(self, res: CheckResult, package: str) -> None:
        manifest_path = _manifest_path(package)
        _check_exports_surface(res, manifest_path, self.load_manifest(package), self.subject)

        owned = sorted(path for path in self.story_files if story_docs.under_package(path, package))
        for story_file in owned:
            self._check_story_imports(res, story_file)

        governing = sorted({m for f in owned if (m := _governing_manifest(f, self.path_set)) is not None})
        for governing_manifest in governing:
            self._check_alias_escapes(res, governing_manifest)

    def _check_story_imports(self, res: CheckResult, story_file: str) -> None:
        content = self.ctx.file(self.repo, story_file)
        if content is None:
            return
        for specifier in _import_specifiers(content):
            if self._is_outside_seam(specifier):
                res.fail(f"{story_file}: story test imports outside the fixtures seam — {specifier!r}")

    def _is_outside_seam(self, specifier: str) -> bool:
        if specifier.startswith(_SEAM_SPECIFIER_PREFIXES):
            return False
        if specifier.startswith(_PATH_SPECIFIER_PREFIXES):
            return True
        return any(specifier == name or specifier.startswith(f"{name}/") for name in self.workspace_names)

    def _check_alias_escapes(self, res: CheckResult, manifest_path: str) -> None:
        imports = _parse_manifest(self.ctx.file(self.repo, manifest_path)).get("imports")
        if not isinstance(imports, dict):
            return
        for alias, value in sorted(imports.items()):
            for target in _alias_targets(value):
                if ".." in target.split("/"):
                    res.fail(f"{manifest_path}: imports alias escapes the test package — {alias!r} -> {target!r}")
