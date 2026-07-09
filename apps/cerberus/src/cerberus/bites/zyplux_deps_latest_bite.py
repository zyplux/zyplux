"""The `zyplux_deps_latest` bite: org-published artifacts must be consumed at their latest release.

Artifacts are detected by namespace — `@zyplux/` on npm, `zyplux-*` on PyPI,
`ghcr.io/zyplux/` on GHCR — so newly published packages are covered without
touching cerberus. Consumption is read from resolved/pinned versions
(lockfiles, `==` pins, image tags), never from declared ranges; workspace-local
members are the repo's own code and are ignored. There is deliberately no
`--fix`: bumping is `just upgrade`'s job.

Confirmed lookups are cached for an hour under the user cache dir; a cache
entry is only trusted when it is fresh and matches every used version of its
artifact, so a lag finding always comes from a live registry answer.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cerberus import registries
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from cerberus.context import Context

ID = "zyplux_deps_latest"
SUMMARY = "every @zyplux/* npm package, zyplux-* PyPI distribution, and ghcr.io/zyplux image is at latest release"
SCOPE = Scope.CONTENT

_NPM_LOCKED = re.compile(r'"(@zyplux/[\w.-]+)@(\d[\w.+-]*)"')
_PYPI_PINNED = re.compile(r"\b(zyplux-[\w.-]+)==(\d[\w.!+-]*)")
_GHCR_IMAGE = re.compile(r"ghcr\.io/(zyplux/[\w./-]+?):([\w.-]+)")
_FLOATING_IMAGE_TAG = "latest"
_MAX_CONCURRENT_LOOKUPS = 8
_CACHE_TTL_SECONDS = 60 * 60

_FETCHERS: dict[str, Callable[[str], str]] = {
    "npm": registries.fetch_latest_npm,
    "pypi": registries.fetch_latest_pypi,
    "ghcr": registries.fetch_latest_ghcr,
}


@dataclass(frozen=True, order=True)
class Usage:
    kind: str
    name: str
    version: str
    location: str

    @property
    def label(self) -> str:
        return f"ghcr.io/{self.name}" if self.kind == "ghcr" else self.name


def _npm_usages(lock: str) -> Iterator[Usage]:
    for name, version in _NPM_LOCKED.findall(lock):
        yield Usage("npm", name, version, "bun.lock")


def _uv_lock_usages(lock: str) -> Iterator[Usage]:
    try:
        packages = tomllib.loads(lock).get("package", [])
    except tomllib.TOMLDecodeError:
        return
    for package in packages:
        name, version, source = package.get("name", ""), package.get("version"), package.get("source", {})
        if name.startswith("zyplux-") and "registry" in source and isinstance(version, str):
            yield Usage("pypi", name, version, "uv.lock")


def _pinned_text_usages(text: str, location: str) -> Iterator[Usage]:
    for name, version in _PYPI_PINNED.findall(text):
        yield Usage("pypi", name, version, location)
    for image, tag in _GHCR_IMAGE.findall(text):
        if tag != _FLOATING_IMAGE_TAG:
            yield Usage("ghcr", image, tag, location)


def _collect_usages(repo: Repo, ctx: Context) -> list[Usage]:
    usages: set[Usage] = set()
    if (bun_lock := ctx.file(repo, "bun.lock")) is not None:
        usages.update(_npm_usages(bun_lock))
    if (uv_lock := ctx.file(repo, "uv.lock")) is not None:
        usages.update(_uv_lock_usages(uv_lock))
    if (justfile := ctx.file(repo, "justfile")) is not None:
        usages.update(_pinned_text_usages(justfile, "justfile"))
    for name, workflow in ctx.workflows(repo).items():
        usages.update(_pinned_text_usages(workflow, f".github/workflows/{name}"))
    return sorted(usages)


def _fetch_latest_versions(
    artifacts: Iterable[tuple[str, str]],
) -> dict[tuple[str, str], str | registries.RegistryLookupError]:
    def lookup(artifact: tuple[str, str]) -> str | registries.RegistryLookupError:
        kind, name = artifact
        try:
            return _FETCHERS[kind](name)
        except registries.RegistryLookupError as err:
            return err

    ordered = sorted(artifacts)
    if not ordered:
        return {}
    with ThreadPoolExecutor(max_workers=min(_MAX_CONCURRENT_LOOKUPS, len(ordered))) as pool:
        return dict(zip(ordered, pool.map(lookup, ordered), strict=True))


@dataclass(frozen=True)
class _CacheEntry:
    latest: str
    fetched_at: float


def _cache_file() -> Path:
    cache_home = os.environ.get("XDG_CACHE_HOME")
    base = Path(cache_home) if cache_home else Path.home() / ".cache"
    return base / "cerberus" / "registry_latest.json"


def _cache_key(artifact: tuple[str, str]) -> str:
    kind, name = artifact
    return f"{kind}:{name}"


def _load_cache(cache_file: Path) -> dict[str, _CacheEntry]:
    try:
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    if not isinstance(raw, dict):
        return {}
    entries = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        latest, fetched_at = value.get("latest"), value.get("fetched_at")
        if isinstance(latest, str) and isinstance(fetched_at, int | float):
            entries[str(key)] = _CacheEntry(latest, float(fetched_at))
    return entries


def _save_cache(cache_file: Path, entries: dict[str, _CacheEntry]) -> None:
    payload = {key: {"fetched_at": entry.fetched_at, "latest": entry.latest} for key, entry in sorted(entries.items())}
    with contextlib.suppress(OSError):
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(payload), encoding="utf-8")


def _confirmed_by_cache(usages: list[Usage], cache: dict[str, _CacheEntry], now: float) -> dict[tuple[str, str], str]:
    used_versions: dict[tuple[str, str], set[str]] = {}
    for usage in usages:
        used_versions.setdefault((usage.kind, usage.name), set()).add(usage.version)
    confirmed = {}
    for artifact, versions in used_versions.items():
        entry = cache.get(_cache_key(artifact))
        if entry is not None and now - entry.fetched_at < _CACHE_TTL_SECONDS and versions == {entry.latest}:
            confirmed[artifact] = entry.latest
    return confirmed


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    usages = _collect_usages(repo, ctx)
    if not usages:
        res.ok("no zyplux-published artifacts in use")
        return res

    cache_file = _cache_file()
    cache = _load_cache(cache_file)
    now = time.time()
    confirmed = _confirmed_by_cache(usages, cache, now)
    fetched = _fetch_latest_versions({(usage.kind, usage.name) for usage in usages} - confirmed.keys())
    fresh = {
        _cache_key(artifact): _CacheEntry(latest, now)
        for artifact, latest in fetched.items()
        if isinstance(latest, str)
    }
    if fresh:
        _save_cache(cache_file, {**cache, **fresh})

    latest_versions: dict[tuple[str, str], str | registries.RegistryLookupError] = {**confirmed, **fetched}
    labels = {(usage.kind, usage.name): usage.label for usage in usages}
    for artifact, outcome in sorted(latest_versions.items()):
        if isinstance(outcome, registries.RegistryLookupError):
            res.error(f"could not determine the latest `{labels[artifact]}`: {outcome}")
    for usage in usages:
        latest = latest_versions[usage.kind, usage.name]
        if isinstance(latest, str) and usage.version != latest:
            res.fail(f"`{usage.label}` is {usage.version} in {usage.location}, latest is {latest}; run `just upgrade`")

    if not res.problems:
        res.ok("every zyplux artifact is at its latest release")
    return res
