from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from airlock import proc
from airlock.actions import parse_stable_version
from airlock.errors import RELEASE_ERRORS
from airlock.registries import fetch_latest
from airlock.targets import load_specs, parse_manifest, parse_version

from cerberus.model import Finding, Status

if TYPE_CHECKING:
    from airlock.contracts import TargetSpec
    from semantic_version import Version


def load_git_file(root: Path, ref: str, file: str) -> str | None:
    entry = proc.run("git", "ls-tree", "--name-only", ref, "--", file, cwd=root)
    return proc.run("git", "show", f"{ref}:{file}", cwd=root) if entry else None


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


def validate_published(
    root: Path, target: TargetSpec, version: Version, baseline: tuple[str, Version] | None
) -> list[Finding]:
    try:
        latest = fetch_latest(target, root / Path(target.version.file).parent)
        published = None if latest is None else parse_stable_version(latest)
    except RELEASE_ERRORS as exc:
        return [Finding(Status.ERROR, f"{target.label}: cannot determine the latest published version: {exc}")]
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
        changed = proc.run("git", "diff", "--name-only", tag, "--", *target.surface, cwd=root)
    except RELEASE_ERRORS as exc:
        return [Finding(Status.ERROR, f"{target.label}: cannot diff against {tag}: {exc}")]
    return (
        [
            Finding(
                Status.FAIL,
                f"{target.label}: surface changed since {tag} but version is still {version} — "
                f"bump it (e.g. {version.next_patch()})",
            )
        ]
        if changed
        else []
    )


def load_base_version(root: Path, base: str, previous: TargetSpec) -> Version:
    content = load_git_file(root, base, previous.version.file)
    if content is None:
        message = f"version file {previous.version.file} is missing"
        raise ValueError(message)
    return parse_stable_version(parse_version(content, previous.version))


def validate_target(root: Path, target: TargetSpec, base: str | None, base_specs: list[TargetSpec]) -> list[Finding]:
    try:
        version = parse_stable_version(
            parse_version((root / target.version.file).read_text(encoding="utf-8"), target.version)
        )
    except RELEASE_ERRORS as exc:
        return [Finding(Status.FAIL, f"{target.label}: cannot read {target.version.file}: {exc}")]
    baseline = None
    previous = next((spec for spec in base_specs if spec.kind == target.kind and spec.label == target.label), None)
    if base is not None and previous is not None:
        try:
            base_version = load_base_version(root, base, previous)
        except RELEASE_ERRORS as exc:
            return [Finding(Status.ERROR, f"{target.label}: cannot compare the target branch {base}: {exc}")]
        if version < base_version:
            return [Finding(Status.FAIL, f"{target.label}: version must not decrease from {base} ({base_version})")]
        baseline = f"{base} ({base_version})", base_version
    return validate_published(root, target, version, baseline)


def check_release_surface(root: Path | None = None, base: str | None = None) -> list[Finding]:
    try:
        return validate_surface(root or proc.find_root(), base)
    except RELEASE_ERRORS as exc:
        return [Finding(Status.ERROR, f"cannot check release surfaces: {exc}")]


def validate_surface(root: Path, base: str | None) -> list[Finding]:
    branch = os.getenv("GITHUB_BASE_REF")
    base = base or (f"origin/{branch}" if branch else None)
    specs = load_specs(root)
    manifest = load_git_file(root, base, "airlock-targets.toml") if base and specs else None
    base_specs = parse_manifest(manifest) if manifest is not None else []
    findings = [finding for spec in specs for finding in validate_target(root, spec, base, base_specs)]
    if all(finding.status == Status.PASS for finding in findings):
        findings.append(Finding(Status.PASS, "every published target's version tracks its surface"))
    return findings
