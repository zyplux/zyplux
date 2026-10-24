from __future__ import annotations

import operator
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from semantic_version import Version

from airlock import github, proc
from airlock.contracts import ACTION_RELEASES, ActionSpec

if TYPE_CHECKING:
    from airlock.contracts import ReleaseTarget

ACTION_POLL_ATTEMPTS = 12


def parse_remote_tag(listing: str, ref: str) -> str:
    lines = listing.splitlines()
    for candidate in (f"{ref}^{{}}", ref):
        for line in lines:
            if line.endswith(f"\t{candidate}"):
                return line.split("\t", 1)[0]
    return ""


def parse_stable_version(version: str) -> Version:
    try:
        parsed = Version(version)
    except ValueError as exc:
        msg = f"version '{version}' is not stable semver"
        raise ValueError(msg) from exc
    if parsed.prerelease:
        msg = f"version '{version}' is not stable semver"
        raise ValueError(msg)
    return parsed


def fetch_action_releases(spec: ActionSpec) -> list[tuple[str, Version]]:
    response = proc.run("gh", "api", "--paginate", "--slurp", f"repos/{spec.repository}/releases?per_page=100")
    releases = []
    for page in ACTION_RELEASES.validate_json(response):
        for release in page:
            if release.draft or release.prerelease or not release.tag_name.startswith(spec.tag_prefix):
                continue
            try:
                version = parse_stable_version(release.tag_name.removeprefix(spec.tag_prefix))
            except ValueError:
                continue
            releases.append((release.tag_name, version))
    return sorted(releases, key=operator.itemgetter(1), reverse=True)


@dataclass(frozen=True)
class ActionAlias:
    commit: str
    previous_sha: str
    ref: str
    release_ref: str


def resolve_action_alias(target: ReleaseTarget) -> ActionAlias | None:
    spec = target.spec
    if not isinstance(spec, ActionSpec):
        msg = "action publication requires an action target"
        raise TypeError(msg)
    try:
        version = parse_stable_version(target.version)
    except ValueError as exc:
        msg = f"action version '{target.version}' must be stable semver"
        raise ValueError(msg) from exc
    ref = f"refs/tags/{spec.tag_prefix}{version.major}"
    previous_sha = parse_remote_tag(proc.run("git", "ls-remote", "origin", ref), ref)
    releases = fetch_action_releases(spec)
    if all(tag != target.tag for tag, _ in releases):
        return None
    latest = next(tag for tag, candidate in releases if candidate.major == version.major)
    release_ref = f"refs/tags/{latest}"
    commit = parse_remote_tag(proc.run("git", "ls-remote", "origin", f"{release_ref}*"), release_ref)
    if not commit:
        msg = f"published action tag {latest} is missing"
        raise ValueError(msg)
    return ActionAlias(commit, previous_sha, ref, release_ref)


def is_action_published(target: ReleaseTarget) -> bool:
    alias = resolve_action_alias(target)
    return alias is not None and alias.previous_sha == alias.commit


def publish_action(target: ReleaseTarget, notes: str | None) -> None:
    try:
        parse_stable_version(target.version)
    except ValueError as exc:
        msg = f"action version '{target.version}' must be stable semver"
        raise ValueError(msg) from exc
    if notes is not None and github.load_release(target.tag) is None:
        github.create_release(target.tag, notes, proc.run("git", "rev-parse", "HEAD"))
    for attempt in range(ACTION_POLL_ATTEMPTS):
        alias = resolve_action_alias(target)
        if alias is not None:
            break
        if attempt < ACTION_POLL_ATTEMPTS - 1:
            time.sleep(5)
    else:
        msg = f"published GitHub release {target.tag} was not visible after waiting; retry publication"
        raise ValueError(msg)
    if alias.previous_sha == alias.commit:
        return
    proc.run("git", "fetch", "--no-tags", "origin", alias.release_ref)
    commit = proc.run("git", "rev-parse", "FETCH_HEAD^{commit}")
    if commit != alias.commit:
        msg = f"action tag {alias.release_ref} changed during publication"
        raise ValueError(msg)
    proc.run("git", "push", f"--force-with-lease={alias.ref}:{alias.previous_sha}", "origin", f"{commit}:{alias.ref}")
