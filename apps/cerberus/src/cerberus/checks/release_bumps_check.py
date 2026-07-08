from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cerberus import registries
from cerberus.model import CheckResult, Repo, Scope
from cerberus.source import GitHistoryUnavailableError

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.context import Context

ID = "release-bumps"
SUMMARY = "a published target's version is bumped whenever its release surface changes"
SCOPE = Scope.GIT_HISTORY

_MANIFEST = "release-targets.toml"
_TARGET_KEY = "target"
_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)")
_GHCR_HOST_PREFIX = "ghcr.io/"

_FETCHERS: dict[str, Callable[[str], str]] = {
    "npm": registries.fetch_latest_npm,
    "pypi": registries.fetch_latest_pypi,
    "ghcr": registries.fetch_latest_ghcr,
}

Semver = tuple[int, int, int]


@dataclass(frozen=True)
class _Target:
    label: str
    kind: str
    tag_prefix: str
    version_file: str
    version_json: str | None
    version_regex: str | None
    surface: tuple[str, ...]

    @property
    def registry_name(self) -> str:
        return self.label.removeprefix(_GHCR_HOST_PREFIX) if self.kind == "ghcr" else self.label


class _ManifestError(ValueError):
    def __init__(self, key: str, found: object) -> None:
        super().__init__(f"{_MANIFEST} has no [[{key}]] array (found {found!r})")


def _parse_targets(manifest: str) -> list[_Target]:
    raw = tomllib.loads(manifest).get(_TARGET_KEY)
    if not isinstance(raw, list):
        raise _ManifestError(_TARGET_KEY, raw)
    targets = []
    for entry in raw:
        version = entry["version"]
        targets.append(
            _Target(
                label=entry["label"],
                kind=entry["kind"],
                tag_prefix=entry["tag_prefix"],
                version_file=version["file"],
                version_json=version.get("json"),
                version_regex=version.get("regex"),
                surface=tuple(entry.get("surface", [])),
            )
        )
    return targets


def _read_version(content: str, target: _Target) -> str | None:
    if target.version_json is not None:
        value: object = json.loads(content)
        for key in target.version_json.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(key)
        return value if isinstance(value, str) else None
    if target.version_regex is not None:
        match = re.search(target.version_regex, content, re.MULTILINE)
        return match.group(1) if match else None
    return None


def _parse_semver(version: str) -> Semver | None:
    match = _SEMVER.match(version)
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def _current_semver(repo: Repo, ctx: Context, target: _Target, res: CheckResult) -> tuple[Semver, str] | None:
    content = ctx.file(repo, target.version_file)
    if content is None:
        res.fail(f"{target.label}: version file {target.version_file} is missing")
        return None
    try:
        version = _read_version(content, target)
    except json.JSONDecodeError as exc:
        res.fail(f"{target.label}: {target.version_file} is not valid JSON: {exc}")
        return None
    if version is None:
        res.fail(f"{target.label}: no version found in {target.version_file}")
        return None
    current = _parse_semver(version)
    if current is None:
        res.fail(f"{target.label}: version {version!r} is not semver")
        return None
    return current, version


def _fetch_latest_published(target: _Target) -> tuple[Semver, str]:
    """Raises RegistryNotFoundError if nothing is published yet, RegistryLookupError on other failures."""
    version = _FETCHERS[target.kind](target.registry_name)
    semver = _parse_semver(version)
    if semver is None:
        failure = f"published version {version!r} is not semver"
        raise registries.RegistryLookupError(failure)
    return semver, version


def _verify(repo: Repo, ctx: Context, target: _Target, res: CheckResult) -> None:
    resolved = _current_semver(repo, ctx, target, res)
    if resolved is None:
        return
    current, version = resolved

    try:
        latest = _fetch_latest_published(target)
    except registries.RegistryNotFoundError:
        res.ok(f"{target.label}: not yet released")
        return
    except registries.RegistryLookupError as exc:
        res.error(f"{target.label}: cannot determine the latest published version: {exc}")
        return

    latest_semver, latest_version = latest
    if current > latest_semver:
        res.ok(f"{target.label}: {version} is ahead of published {latest_version}")
        return
    if current < latest_semver:
        res.fail(f"{target.label}: version {version} is below published {latest_version}")
        return

    latest_tag = f"{target.tag_prefix}{latest_version}"
    try:
        changed = ctx.changed_paths(repo, latest_tag, target.surface)
    except GitHistoryUnavailableError as exc:
        res.error(f"{target.label}: cannot diff against {latest_tag}: {exc}")
        return
    if changed:
        major, minor, patch = current
        res.fail(
            f"{target.label}: surface changed since {latest_tag} but version is still {version} — "
            f"bump it (e.g. {major}.{minor}.{patch + 1})"
        )


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    manifest = ctx.file(repo, _MANIFEST)
    if manifest is None:
        res.skip(f"no {_MANIFEST} — repo publishes nothing")
        return res
    try:
        targets = _parse_targets(manifest)
    except (tomllib.TOMLDecodeError, KeyError, TypeError, ValueError) as exc:
        res.error(f"{_MANIFEST} is malformed: {exc}")
        return res

    for target in targets:
        _verify(repo, ctx, target, res)

    if not res.problems:
        res.ok("every published target's version tracks its surface")
    return res
