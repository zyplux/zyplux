from __future__ import annotations

import json
import os
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer

from airlock.contracts import ReleaseBatch
from airlock.notes import load_prepared_targets, prepare_release
from airlock.npm import publish_npm_targets
from airlock.releases import bootstrap_npm, build_batches, load_pending, publish_batch, publish_tagged
from airlock.surface import CHECK_ERRORS, check_release_surface
from airlock.targets import resolve_tag

app = typer.Typer(
    help="Prepare and publish reviewed workspace releases.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def print_version(*, is_requested: bool) -> None:
    if is_requested:
        typer.echo(version("zyplux-airlock"))
        raise typer.Exit


@app.callback()
def configure_cli(
    *,
    _show_version: Annotated[bool, typer.Option("--version", callback=print_version, is_eager=True)] = False,
) -> None:
    pass


@app.command("av", hidden=True)
@app.command(help="Check that a release tag matches its target's declared version.")
def assert_tag_version(tag: str) -> None:
    target = resolve_tag(tag)
    typer.echo(f"{target.spec.label} {target.version} matches {tag}")


@app.command("pk", hidden=True)
@app.command(help="Print the publication kind of the target that owns a release tag.")
def print_tag_kind(tag: str) -> None:
    typer.echo(resolve_tag(tag).spec.kind)


@app.command("bn", hidden=True)
@app.command("bootstrap-npm-target", help="First-publish an npm target using local registry authentication.")
def bootstrap(label: str) -> None:
    bootstrap_npm(label)


@app.command("check", hidden=True)
@app.command(help="Validate consumed change intents, synchronized versions and release notes.")
def check_release_notes() -> None:
    load_prepared_targets()


@app.command("notes", hidden=True)
@app.command(help="Print prepared release metadata and changelog entries as JSON.")
def list_prepared_releases() -> None:
    typer.echo(
        json.dumps(
            [
                {
                    "kind": target.spec.kind,
                    "label": target.spec.label,
                    "notes": notes,
                    "tag": target.tag,
                    "version": target.version,
                }
                for target, notes in load_prepared_targets()
            ],
            separators=(",", ":"),
        )
    )


@app.command("prepare", hidden=True)
@app.command("prepare-release", help="Prepare versions, changelogs and lockfiles for review.")
def prepare() -> None:
    prepare_release()


@app.command(help="Require single-step version bumps for changed release surfaces.")
def check_surface(
    *,
    base: Annotated[str | None, typer.Option()] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    findings = check_release_surface(base=base)
    if as_json:
        typer.echo(json.dumps([asdict(finding) for finding in findings]))
    else:
        for finding in findings:
            typer.echo(f"{finding.status}: {finding.message}")
    if any(finding.status in {"fail", "error"} for finding in findings):
        msg = "release surface validation failed"
        raise ValueError(msg)


@app.command(help="Select pending releases and emit isolated publication batches.")
def plan(tag: Annotated[str | None, typer.Option()] = None) -> None:
    batches = build_batches(load_pending(tag))
    matrix = json.dumps({"include": [batch.model_dump() for batch in batches]}, separators=(",", ":"))
    typer.echo(matrix)
    destination = os.getenv("GITHUB_OUTPUT")
    if destination:
        with Path(destination).open("a", encoding="utf-8") as stream:
            stream.write(f"matrix={matrix}\npending={str(bool(batches)).lower()}\n")


@app.command(help="Publish exactly one planned batch and finalize its GitHub release.")
def publish(batch: Annotated[str, typer.Option()]) -> None:
    publish_batch(ReleaseBatch.model_validate_json(batch))


@app.command("publish-npm", help="Publish npm targets in dependency order and reconcile their GitHub releases.")
def publish_npm() -> None:
    publish_npm_targets([(target, notes) for target, notes in load_prepared_targets() if target.spec.kind == "npm"])


@app.command("pt", hidden=True)
@app.command("publish-tagged-target", help="Publish the npm, PyPI, GHCR or action target that owns a release tag.")
def publish_target(tag: str, *, should_release: Annotated[bool, typer.Option("--release")] = False) -> None:
    publish_tagged(tag, should_release=should_release)


def main() -> None:
    try:
        app()
    except CHECK_ERRORS as exc:
        prefix = "ENOENT: " if isinstance(exc, FileNotFoundError) else ""
        typer.echo(f"error: {prefix}{exc}", err=True)
        raise SystemExit(1) from exc
