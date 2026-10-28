from __future__ import annotations

from contextlib import chdir
from typing import TYPE_CHECKING

import typer
from airlock.notes import prepare_release
from airlock.proc import find_root, run
from airlock.targets import load_targets

from clipy import code_metrics

if TYPE_CHECKING:
    from pathlib import Path


def prepare_fingerprint(path: Path) -> None:
    root = find_root(path)

    def write_reports() -> None:
        run("pnpm", "exec", "cz", "workspace-graph", str(root), cwd=root)
        typer.echo(f"wrote {code_metrics.write_report(root)}")

    if (root / "airlock-targets.toml").is_file() and load_targets(root):
        with chdir(root):
            prepare_release(before_fingerprints=write_reports)
    else:
        typer.echo("No release targets; preparing repository reports.")
        write_reports()
