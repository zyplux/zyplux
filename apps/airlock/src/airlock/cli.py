from __future__ import annotations

import json
import os
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer

from airlock.contracts import ReleaseBatch
from airlock.errors import RELEASE_ERRORS
from airlock.notes import load_prepared_targets, prepare_release
from airlock.releases import build_batch, load_pending, publish_batch

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


@app.command(help="Validate consumed change intents, synchronized versions and release notes.")
def check() -> None:
    load_prepared_targets()


@app.command(help="Prepare versions, changelogs and lockfiles for review.")
def prepare() -> None:
    prepare_release()


@app.command(help="Select pending releases and emit isolated publication batches.")
def plan(tag: Annotated[str | None, typer.Option()] = None) -> None:
    batches = [build_batch(target) for target in load_pending(tag)]
    matrix = json.dumps({"include": [batch.model_dump() for batch in batches]}, separators=(",", ":"))
    typer.echo(matrix)
    destination = os.getenv("GITHUB_OUTPUT")
    if destination:
        with Path(destination).open("a", encoding="utf-8") as stream:
            stream.write(f"matrix={matrix}\npending={str(bool(batches)).lower()}\n")


@app.command(help="Publish exactly one planned batch and finalize its GitHub release.")
def publish(batch: Annotated[str, typer.Option()]) -> None:
    publish_batch(ReleaseBatch.model_validate_json(batch))


def main() -> None:
    try:
        app()
    except RELEASE_ERRORS as exc:
        prefix = "ENOENT: " if isinstance(exc, FileNotFoundError) else ""
        typer.echo(f"error: {prefix}{exc}", err=True)
        raise SystemExit(1) from exc
