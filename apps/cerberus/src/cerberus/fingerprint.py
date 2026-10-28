from __future__ import annotations

from contextlib import chdir
from typing import TYPE_CHECKING

import typer
from airlock.notes import prepare_release
from airlock.proc import find_root
from airlock.targets import load_targets

from cerberus import code_metrics, workspace_graph

if TYPE_CHECKING:
    from pathlib import Path


def prepare_fingerprint(path: Path) -> None:
    root = find_root(path)
    if (root / "airlock-targets.toml").is_file() and load_targets(root):
        with chdir(root):
            prepare_release()
    else:
        typer.echo("No release targets; preparing repository reports.")
    typer.echo(f"wrote {workspace_graph.write_report(root)}")
    typer.echo(f"wrote {code_metrics.write_report(root)}")
