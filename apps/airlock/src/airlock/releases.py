from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import typer

from airlock import github, proc, pypi
from airlock.actions import publish_action
from airlock.containers import is_container_published, publish_container
from airlock.content_hash import build_archives, validate_content_hash
from airlock.contracts import ActionSpec, ReleaseBatch
from airlock.notes import load_prepared_targets
from airlock.npm import publish_npm
from airlock.registries import is_published, wait_for_dependencies
from airlock.targets import load_targets

if TYPE_CHECKING:
    from airlock.contracts import ReleaseTarget


def build_batch(target: ReleaseTarget) -> ReleaseBatch:
    return ReleaseBatch(
        environment=target.environment,
        id=f"{target.spec.kind}-{target.spec.tag_prefix.removesuffix('-v')}",
        kind=target.spec.kind,
        runner="ubuntu-latest",
        tags=[target.tag],
    )


def load_pending(tag: str | None) -> list[ReleaseTarget]:
    prepared = load_prepared_targets()
    selected = [target for target, _ in prepared if tag is None or target.tag == tag]
    if tag is not None and not selected:
        msg = f"no configured release target matches '{tag}'"
        raise ValueError(msg)
    return [
        target
        for target in selected
        if not (
            is_container_published(target)
            if target.spec.kind == "ghcr"
            else is_published(target) and github.load_release(target.tag) is not None
        )
    ]


def publish_prepared(target: ReleaseTarget, notes: str) -> None:
    if target.spec.kind in {"action", "ghcr"}:
        validate_content_hash(target)
    if isinstance(target.spec, ActionSpec):
        publish_action(target, notes)
        return
    if target.spec.kind == "ghcr":
        publish_container(target, notes)
        return
    if target.spec.kind == "npm":
        publish_npm(target)
    elif is_published(target):
        if github.load_release(target.tag) is None:
            validate_content_hash(target)
        typer.echo(f"{target.spec.label} {target.version} is already published; nothing to do")
    else:
        typer.echo(f"Publishing {target.spec.label} {target.version} to {target.spec.kind} ...")
        with TemporaryDirectory(prefix="release-pypi-") as directory:
            archives = build_archives(target, Path(directory))
            validate_content_hash(target, archives)
            wait_for_dependencies(pypi.load_dependencies(target, archives))
            proc.run("uv", "publish", "--check-url", "https://pypi.org/simple/", str(Path(directory) / "*"))
        typer.echo(f"Published {target.spec.label} {target.version}")
    if github.load_release(target.tag) is None:
        github.create_release(target.tag, notes, proc.run("git", "rev-parse", "HEAD"))


def publish_batch(batch: ReleaseBatch) -> None:
    tag = batch.tags[0]
    target = next((target for target in load_targets() if target.tag == tag), None)
    if target is None:
        msg = f"no configured release target matches '{tag}'"
        raise ValueError(msg)
    if build_batch(target) != batch:
        msg = "batch does not match the configured publication group"
        raise ValueError(msg)
    [(target, notes)] = load_prepared_targets([target])
    has_published = False
    try:
        publish_prepared(target, notes)
        has_published = True
    finally:
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write(f"### {batch.id}: {'published' if has_published else 'failed'}\n\n- {target.tag}\n\n")
