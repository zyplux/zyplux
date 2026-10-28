from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from airlock import github
from airlock.contracts import PackageSpec
from airlock.errors import RELEASE_ERRORS
from airlock.registries import has_package_artifacts
from airlock.targets import build_release_target, parse_manifest, parse_package, parse_stable_version, resolve_repo_path

from cerberus.model import Finding, Status
from cerberus.source import GitHistoryUnavailableError

if TYPE_CHECKING:
    from airlock.contracts import ReleaseTarget, TargetSpec
    from semantic_version import Version

    from cerberus.context import Context
    from cerberus.model import Repo


@dataclass(frozen=True)
class PublishedTarget:
    target: TargetSpec
    version: Version | None


def validate_bump(package_name: str, version: Version, baseline: tuple[str, Version]) -> list[Finding]:
    label, previous = baseline
    if version == previous:
        return []
    if version < previous:
        return [Finding(Status.FAIL, f"{package_name}: version {version} is below {label}")]
    steps = (previous.next_patch(), previous.next_minor(), previous.next_major())
    if version in steps:
        return [Finding(Status.PASS, f"{package_name}: {version} is ahead of {label}")]
    patch, minor, major = steps
    return [
        Finding(
            Status.FAIL,
            f"{package_name}: version {version} skips ahead of {label} — bump one step ({patch}, {minor}, or {major})",
        )
    ]


def load_specs_at_ref(repo: Repo, ctx: Context, ref: str) -> list[TargetSpec]:
    manifest = ctx.file_at_ref(repo, ref, "airlock_targets.toml")
    if manifest is not None:
        return parse_manifest(manifest, is_historical=True)
    manifest = ctx.file_at_ref(repo, ref, "airlock-targets.toml")
    return [
        spec if "includes" in spec.model_fields_set else spec.model_copy(update={"includes": ["**/*"]})
        for spec in (parse_manifest(manifest, is_historical=True) if manifest is not None else [])
    ]


def has_content_changes(repo: Repo, ctx: Context, target: TargetSpec, tag: str) -> bool:
    previous = next(
        (spec for spec in load_specs_at_ref(repo, ctx, tag) if spec.tag_prefix == target.tag_prefix),
        None,
    )
    return (
        previous is not None
        and previous.includes == target.includes
        and previous.hash is not None
        and target.hash is not None
        and target.hash != previous.hash
    )


def validate_published(
    repo: Repo,
    ctx: Context,
    lookup: PublishedTarget,
    release: ReleaseTarget,
    baseline: tuple[str, Version] | None,
) -> list[Finding]:
    target, published = lookup.target, lookup.version
    version = parse_stable_version(release.version)
    if published is None:
        return (
            [Finding(Status.PASS, f"{release.package_name}: not yet released")]
            if baseline is None
            else validate_bump(release.package_name, version, baseline)
        )
    if baseline is None or published >= baseline[1]:
        baseline = f"published {published}", published
    if version != published:
        return validate_bump(release.package_name, version, baseline)
    tag = f"{target.tag_prefix}{published}"
    try:
        changed = has_content_changes(repo, ctx, target, tag)
    except (*RELEASE_ERRORS, GitHistoryUnavailableError) as exc:
        return [Finding(Status.ERROR, f"{release.package_name}: cannot compare contents against {tag}: {exc}")]
    return (
        [
            Finding(
                Status.FAIL,
                f"{release.package_name}: contents changed since {tag} but version is still {version} — "
                f"bump it (e.g. {version.next_patch()})",
            )
        ]
        if changed
        else []
    )


def load_base_version(repo: Repo, ctx: Context, base: str, previous: TargetSpec) -> Version:
    content = ctx.file_at_ref(repo, base, previous.manifest)
    if content is None:
        message = f"manifest {previous.manifest} is missing"
        raise ValueError(message)
    return parse_stable_version(parse_package(content, previous.manifest).version)


def validate_registry_repair(target: ReleaseTarget, previous: TargetSpec) -> list[Finding]:
    if previous.includes == target.spec.includes and (previous.hash is None or target.spec.hash == previous.hash):
        return []
    try:
        if not has_package_artifacts(target):
            return []
    except RELEASE_ERRORS as exc:
        return [Finding(Status.ERROR, f"{target.package_name}: cannot validate registry artifacts: {exc}")]
    return [
        Finding(
            Status.FAIL,
            f"{target.package_name}: {target.version} already has registry artifacts; "
            "contents differ from the target branch — bump the version",
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
        resolve_repo_path(ctx.source.root, target.manifest)
        content = ctx.file(repo, target.manifest)
        if content is None:
            return [Finding(Status.FAIL, f"{target.name}: manifest {target.manifest} is missing")]
        release = build_release_target(ctx.source.root, target, parse_package(content, target.manifest))
        version = parse_stable_version(release.version)
    except RELEASE_ERRORS as exc:
        return [Finding(Status.FAIL, f"{target.name}: cannot read {target.manifest}: {exc}")]
    baseline = None
    previous = next((spec for spec in base_specs if spec.kind == target.kind and spec.name == target.name), None)
    if base is not None and previous is not None:
        try:
            base_version = load_base_version(repo, ctx, base, previous)
        except (*RELEASE_ERRORS, GitHistoryUnavailableError) as exc:
            return [Finding(Status.ERROR, f"{release.package_name}: cannot compare the target branch {base}: {exc}")]
        if version < base_version:
            return [
                Finding(Status.FAIL, f"{release.package_name}: version must not decrease from {base} ({base_version})")
            ]
        if (
            isinstance(target, PackageSpec)
            and version == base_version
            and (lookup.version is None or lookup.version < version)
        ):
            findings = validate_registry_repair(release, previous)
            if findings:
                return findings
        baseline = f"{base} ({base_version})", base_version
    return validate_published(repo, ctx, lookup, release, baseline)


def check_release_surface(repo: Repo, ctx: Context, base: str | None = None) -> list[Finding]:
    branch = os.getenv("GITHUB_BASE_REF")
    base = base or (f"origin/{branch}" if branch else None)
    try:
        specs = parse_manifest(ctx.file(repo, "airlock_targets.toml") or "")
        base_specs = load_specs_at_ref(repo, ctx, base) if base and specs else []
        history = github.fetch_release_history(directory=ctx.source.root) if specs else []
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
