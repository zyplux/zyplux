from __future__ import annotations

from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from airlock.errors import RELEASE_ERRORS

from clipy import code_metrics

app = typer.Typer(help="Python repository and terminal helpers.", no_args_is_help=True)


def print_version(*, is_requested: bool) -> None:
    if is_requested:
        typer.echo(version("zyplux-clipy"))
        raise typer.Exit


@app.callback()
def configure_cli(
    *,
    _show_version: Annotated[bool, typer.Option("--version", callback=print_version, is_eager=True)] = False,
) -> None:
    pass


@app.command(help="Write tracked code metrics, production scope and BPE token counts as Markdown.")
def stats(
    directory: Annotated[Path, typer.Argument(help="Directory to measure.")] = Path(),
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Report destination.")] = None,
    title: Annotated[str | None, typer.Option(help="Measured scope name in the report heading.")] = None,
) -> None:
    typer.echo(f"wrote {code_metrics.write_report(directory, title=title, out=out)}")


def main() -> None:
    try:
        app()
    except (*RELEASE_ERRORS, code_metrics.GitError) as exc:
        typer.echo(str(exc), err=True)
        raise SystemExit(1) from exc
