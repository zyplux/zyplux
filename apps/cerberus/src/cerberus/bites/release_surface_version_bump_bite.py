from __future__ import annotations

import json
import os
import re
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from cerberus import registries
from cerberus.model import CheckResult, Repo, Scope
from cerberus.source import GitHistoryUnavailableError

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.context import Context

ID = "release_surface_version_bump"
SUMMARY = "a published target's version is bumped by exactly one step whenever its release surface changes"
SCOPE = Scope.GIT_HISTORY

_MANIFEST = "release-targets.toml"
_TARGET_KEY = "target"
_MAX_CONCURRENT_LOOKUPS = 8
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
        kind = entry["kind"]
        if kind not in _FETCHERS:
            label = entry.get("label", "?")
            failure = f"target {label!r} has unknown kind {kind!r} (expected one of {sorted(_FETCHERS)})"
            raise ValueError(failure)
        targets.append(
            _Target(
                label=entry["label"],
                kind=kind,
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


def _format_semver(semver: Semver) -> str:
    return ".".join(map(str, semver))


def _single_step_bumps(latest: Semver) -> tuple[Semver, Semver, Semver]:
    major, minor, patch = latest
    return ((major, minor, patch + 1), (major, minor + 1, 0), (major + 1, 0, 0))


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


def _fetch_latest_published(repo: Repo, ctx: Context, target: _Target) -> tuple[Semver, str]:
    """Raises RegistryNotFoundError if nothing is published yet, RegistryLookupError on other failures."""
    if target.kind == "npm":
        package_path = str(PurePosixPath(target.version_file).parent / "package.json")
        try:
            package = json.loads(ctx.file(repo, package_path) or "{}")
        except json.JSONDecodeError:
            package = None
        publish_config = package.get("publishConfig", {}) if isinstance(package, dict) else {}
        scope = target.registry_name.partition("/")[0]
        registry_key = f"{scope}:registry" if scope.startswith("@") else "registry"
        registry = (
            publish_config.get(registry_key, publish_config.get("registry", "https://registry.npmjs.org"))
            if isinstance(publish_config, dict)
            else None
        )
        if not isinstance(registry, str):
            failure = f"{package_path}: publishConfig.registry must be a string"
            raise registries.RegistryLookupError(failure)
        version = registries.fetch_latest_npm(target.registry_name, registry)
    else:
        version = _FETCHERS[target.kind](target.registry_name)
    semver = _parse_semver(version)
    if semver is None:
        failure = f"published version {version!r} is not semver"
        raise registries.RegistryLookupError(failure)
    return semver, version


def _fetch_all_latest(
    repo: Repo, ctx: Context, targets: list[_Target]
) -> dict[_Target, tuple[Semver, str] | registries.RegistryLookupError]:
    def lookup(target: _Target) -> tuple[Semver, str] | registries.RegistryLookupError:
        try:
            return _fetch_latest_published(repo, ctx, target)
        except registries.RegistryLookupError as err:
            return err

    with ThreadPoolExecutor(max_workers=min(_MAX_CONCURRENT_LOOKUPS, len(targets))) as pool:
        return dict(zip(targets, pool.map(lookup, targets), strict=True))


def _verify_base(
    repo: Repo, ctx: Context, target: _Target, current: Semver, res: CheckResult
) -> tuple[Semver, str] | None:
    base = os.environ.get("GITHUB_BASE_REF")
    if not base:
        return None
    ref = f"origin/{base}"
    try:
        content = ctx.file_at_ref(repo, ref, target.version_file)
        version = _read_version(content, target) if content is not None else None
        changed = ctx.changed_paths(repo, ref, target.surface) if content is not None else []
    except (GitHistoryUnavailableError, json.JSONDecodeError) as exc:
        res.error(f"{target.label}: cannot compare the target branch {ref}: {exc}")
        return None
    if content is None:
        return None
    baseline = _parse_semver(version) if version is not None else None
    if baseline is None:
        res.error(f"{target.label}: {ref} has no semver version")
    elif current < baseline or (current == baseline and changed):
        res.fail(f"{target.label}: release surface requires a version newer than {ref} ({version})")
    else:
        return baseline, f"{ref} ({version})"
    return None


def _verify_bump(target: _Target, current: tuple[Semver, str], baseline: tuple[Semver, str], res: CheckResult) -> None:
    current_semver, version = current
    baseline_semver, baseline_label = baseline
    if current_semver == baseline_semver:
        return
    if current_semver < baseline_semver:
        res.fail(f"{target.label}: version {version} is below {baseline_label}")
        return
    steps = _single_step_bumps(baseline_semver)
    if current_semver in steps:
        res.ok(f"{target.label}: {version} is ahead of {baseline_label}")
    else:
        patch_step, minor_step, major_step = map(_format_semver, steps)
        res.fail(
            f"{target.label}: version {version} skips ahead of {baseline_label} — "
            f"bump one step ({patch_step}, {minor_step}, or {major_step})"
        )


def _verify(
    repo: Repo,
    ctx: Context,
    target: _Target,
    latest: tuple[Semver, str] | registries.RegistryLookupError,
    res: CheckResult,
) -> None:
    resolved = _current_semver(repo, ctx, target, res)
    if resolved is None:
        return
    current, version = resolved

    problem_count = len(res.problems)
    base = _verify_base(repo, ctx, target, current, res)
    if len(res.problems) > problem_count:
        return

    if isinstance(latest, registries.RegistryNotFoundError):
        res.ok(f"{target.label}: not yet released")
        return
    if isinstance(latest, registries.RegistryLookupError):
        res.error(f"{target.label}: cannot determine the latest published version: {latest}")
        return

    latest_semver, latest_version = latest
    baseline = latest_semver, f"published {latest_version}"
    if base is not None and base[0] > baseline[0]:
        baseline = base
    if current != latest_semver:
        _verify_bump(target, resolved, baseline, res)
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

    if not targets:
        res.ok("every published target's version tracks its surface")
        return res

    latest_by_target = _fetch_all_latest(repo, ctx, targets)
    for target in targets:
        _verify(repo, ctx, target, latest_by_target[target], res)

    if not res.problems:
        res.ok("every published target's version tracks its surface")
    return res
