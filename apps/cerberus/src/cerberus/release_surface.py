from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from airlock import github
from airlock.actions import validate_action_repository
from airlock.contracts import ActionSpec, PackageSpec
from airlock.errors import RELEASE_ERRORS
from airlock.registries import has_package_artifacts
from airlock.targets import build_release_target, parse_manifest, parse_stable_version, parse_version, resolve_repo_path

from cerberus.model import Finding, Status
from cerberus.source import GitHistoryUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

    from airlock.contracts import PublishedRelease, TargetSpec
    from semantic_version import Version

    from cerberus.context import Context
    from cerberus.model import Repo


@dataclass(frozen=True)
class PublishedTarget:
    target: TargetSpec
    version: Version | None


def validate_bump(target: TargetSpec, version: Version, baseline: tuple[str, Version]) -> list[Finding]:
    label, previous = baseline
    if version == previous:
        return []
    if version < previous:
        return [Finding(Status.FAIL, f"{target.label}: version {version} is below {label}")]
    steps = (previous.next_patch(), previous.next_minor(), previous.next_major())
    if version in steps:
        return [Finding(Status.PASS, f"{target.label}: {version} is ahead of {label}")]
    patch, minor, major = steps
    return [
        Finding(
            Status.FAIL,
            f"{target.label}: version {version} skips ahead of {label} — bump one step ({patch}, {minor}, or {major})",
        )
    ]


def has_content_changes(repo: Repo, ctx: Context, target: TargetSpec, tag: str) -> bool:
    content = ctx.file_at_ref(repo, tag, "airlock-targets.toml")
    previous = next(
        (
            spec
            for spec in (parse_manifest(content, is_historical=True) if content is not None else [])
            if spec.tag_prefix == target.tag_prefix
        ),
        None,
    )
    return (
        previous is not None
        and previous.content_hash is not None
        and target.content_hash is not None
        and target.content_hash != previous.content_hash
    )


def validate_published(
    repo: Repo,
    ctx: Context,
    lookup: PublishedTarget,
    version: Version,
    baseline: tuple[str, Version] | None,
) -> list[Finding]:
    target, published = lookup.target, lookup.version
    if published is None:
        return (
            [Finding(Status.PASS, f"{target.label}: not yet released")]
            if baseline is None
            else validate_bump(target, version, baseline)
        )
    if baseline is None or published >= baseline[1]:
        baseline = f"published {published}", published
    if version != published:
        return validate_bump(target, version, baseline)
    tag = f"{target.tag_prefix}{published}"
    try:
        changed = has_content_changes(repo, ctx, target, tag)
    except (*RELEASE_ERRORS, GitHistoryUnavailableError) as exc:
        return [Finding(Status.ERROR, f"{target.label}: cannot compare contents against {tag}: {exc}")]
    return (
        [
            Finding(
                Status.FAIL,
                f"{target.label}: contents changed since {tag} but version is still {version} — "
                f"bump it (e.g. {version.next_patch()})",
            )
        ]
        if changed
        else []
    )


def load_base_version(repo: Repo, ctx: Context, base: str, previous: TargetSpec) -> Version:
    content = ctx.file_at_ref(repo, base, previous.version.file)
    if content is None:
        message = f"version file {previous.version.file} is missing"
        raise ValueError(message)
    return parse_stable_version(parse_version(content, previous.version))


def validate_registry_repair(root: Path, target: TargetSpec, previous: TargetSpec, version: Version) -> list[Finding]:
    if previous.content_hash is None or target.content_hash == previous.content_hash:
        return []
    try:
        release = build_release_target(root, target, str(version))
        if not has_package_artifacts(release):
            return []
    except RELEASE_ERRORS as exc:
        return [Finding(Status.ERROR, f"{target.label}: cannot validate registry artifacts: {exc}")]
    return [
        Finding(
            Status.FAIL,
            f"{target.label}: {version} already has registry artifacts; contents differ from the target branch — "
            "bump the version",
        )
    ]


def validate_target(
    repo: Repo,
    ctx: Context,
    lookup: PublishedTarget,
    base: str | None,
    base_specs: list[TargetSpec],
) -> list[Finding]:
    target = lookup.target
    try:
        resolve_repo_path(ctx.source.root, target.version.file)
        content = ctx.file(repo, target.version.file)
        if content is None:
            return [Finding(Status.FAIL, f"{target.label}: version file {target.version.file} is missing")]
        version = parse_stable_version(parse_version(content, target.version))
    except RELEASE_ERRORS as exc:
        return [Finding(Status.FAIL, f"{target.label}: cannot read {target.version.file}: {exc}")]
    baseline = None
    previous = next((spec for spec in base_specs if spec.kind == target.kind and spec.label == target.label), None)
    if base is not None and previous is not None:
        try:
            base_version = load_base_version(repo, ctx, base, previous)
        except (*RELEASE_ERRORS, GitHistoryUnavailableError) as exc:
            return [Finding(Status.ERROR, f"{target.label}: cannot compare the target branch {base}: {exc}")]
        if version < base_version:
            return [Finding(Status.FAIL, f"{target.label}: version must not decrease from {base} ({base_version})")]
        if (
            isinstance(target, PackageSpec)
            and version == base_version
            and (lookup.version is None or lookup.version < version)
        ):
            findings = validate_registry_repair(ctx.source.root, target, previous, version)
            if findings:
                return findings
        baseline = f"{base} ({base_version})", base_version
    return validate_published(repo, ctx, lookup, version, baseline)


def fetch_target_history(specs: list[TargetSpec], directory: Path) -> list[PublishedRelease]:
    for spec in specs:
        if isinstance(spec, ActionSpec):
            validate_action_repository(spec, directory)
    return github.fetch_release_history(directory=directory) if specs else []


def check_release_surface(repo: Repo, ctx: Context, base: str | None = None) -> list[Finding]:
    branch = os.getenv("GITHUB_BASE_REF")
    base = base or (f"origin/{branch}" if branch else None)
    try:
        specs = parse_manifest(ctx.file(repo, "airlock-targets.toml") or "")
        manifest = ctx.file_at_ref(repo, base, "airlock-targets.toml") if base and specs else None
        base_specs = parse_manifest(manifest, is_historical=True) if manifest is not None else []
        history = fetch_target_history(specs, ctx.source.root)
    except (*RELEASE_ERRORS, GitHistoryUnavailableError) as exc:
        return [Finding(Status.ERROR, f"cannot check release contents: {exc}")]
    findings = []
    for spec in specs:
        releases = github.select_releases(history, spec.tag_prefix)
        lookup = PublishedTarget(spec, releases[0][1] if releases else None)
        findings.extend(validate_target(repo, ctx, lookup, base, base_specs))
    if all(finding.status == Status.PASS for finding in findings):
        findings.append(Finding(Status.PASS, "every published target's version tracks its contents"))
    return findings
