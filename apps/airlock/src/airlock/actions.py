from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from airlock import github, proc
from airlock.contracts import ActionSpec
from airlock.targets import parse_stable_version

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
    releases = github.fetch_releases(spec.tag_prefix, spec.repository)
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


def publish_action(target: ReleaseTarget, notes: str) -> None:
    try:
        parse_stable_version(target.version)
    except ValueError as exc:
        msg = f"action version '{target.version}' must be stable semver"
        raise ValueError(msg) from exc
    if github.load_release(target.tag) is None:
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
