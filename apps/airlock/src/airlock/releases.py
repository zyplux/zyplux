from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import typer

from airlock import github, proc
from airlock.actions import publish_action
from airlock.containers import is_container_published, publish_container
from airlock.contracts import ActionSpec, ReleaseBatch
from airlock.notes import load_prepared_targets, load_release_notes, validate_consumed_intents, validate_python_versions
from airlock.npm import publish_npm, publish_npm_targets
from airlock.registries import is_published
from airlock.targets import load_targets, resolve_tag

if TYPE_CHECKING:
    from airlock.contracts import ReleaseTarget


def build_batches(targets: list[ReleaseTarget]) -> list[ReleaseBatch]:
    return [
        ReleaseBatch(
            environment=target.environment,
            id=f"{target.spec.kind}-{target.spec.tag_prefix.removesuffix('-v')}",
            kind=target.spec.kind,
            runner="ubuntu-latest",
            tags=[target.tag],
        )
        for target in targets
    ]


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


def publish_prepared(target: ReleaseTarget, notes: str | None) -> None:
    if isinstance(target.spec, ActionSpec):
        publish_action(target, notes)
        return
    if target.spec.kind == "ghcr":
        if notes is None:
            msg = "container publication requires --release"
            raise ValueError(msg)
        publish_container(target, notes)
        return
    if is_published(target):
        typer.echo(f"{target.spec.label} {target.version} is already published; nothing to do")
    else:
        typer.echo(f"Publishing {target.spec.label} {target.version} to {target.spec.kind} ...")
        if target.spec.kind == "npm":
            publish_npm([target])
        else:
            with TemporaryDirectory(prefix="release-pypi-") as directory:
                proc.run("uv", "build", "--package", target.spec.label, "--out-dir", directory)
                proc.run("uv", "publish", str(Path(directory) / "*"))
        typer.echo(f"Published {target.spec.label} {target.version}")
    if notes is not None and github.load_release(target.tag) is None:
        github.create_release(target.tag, notes, proc.run("git", "rev-parse", "HEAD"))


def publish_tagged(tag: str, *, should_release: bool) -> None:
    target = resolve_tag(tag)
    if should_release:
        validate_consumed_intents()
        validate_python_versions([target])
    notes = load_release_notes(target.directory, target.version) if should_release else None
    publish_prepared(target, notes)


def publish_batch(batch: ReleaseBatch) -> None:
    targets = {target.tag: target for target in load_targets()}
    selected = []
    for tag in batch.tags:
        if tag not in targets:
            msg = f"no configured release target matches '{tag}'"
            raise ValueError(msg)
        selected.append(targets[tag])
    if build_batches(selected) != [batch]:
        msg = "batch does not match the configured publication group"
        raise ValueError(msg)
    releases = load_prepared_targets(selected)
    has_published = False
    try:
        if batch.kind == "npm":
            publish_npm_targets(releases)
        else:
            for target, notes in releases:
                publish_prepared(target, notes)
        has_published = True
    finally:
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write(
                    f"### {batch.id}: {'published' if has_published else 'failed'}\n\n"
                    + "\n".join(f"- {tag}" for tag in batch.tags)
                    + "\n\n"
                )


def bootstrap_npm(label: str) -> None:
    target = next((target for target in load_targets() if target.spec.label == label), None)
    if target is None:
        msg = f"no release target labeled '{label}' in airlock-targets.toml"
        raise ValueError(msg)
    if target.spec.kind != "npm":
        msg = f"bootstrap is npm-only; '{label}' is a {target.spec.kind} target"
        raise ValueError(msg)
    if is_published(target):
        typer.echo(f"{label} {target.version} is already published; no bootstrap needed")
        return
    typer.echo(f"Bootstrapping {label} {target.version} to npm ...")
    publish_npm([target])
    typer.echo(f"Published {label} {target.version}. Configure registry authentication in the release workflow.")
