"""Terminal presentation: minimalist TOON in the log, rich tables/progress bars on an interactive terminal, all routed through the single Console the log pump feeds."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from functools import cache

from rich.box import ROUNDED
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from toon_format import encode

import logs
from logs import log_toon

ACTION_STYLES = {
    "installed": "green",
    "upgraded": "green",
    "changed": "green",
    "up-to-date": "dim",
    "unchanged": "dim",
    "ok": "dim",
    "would install": "yellow",
    "would sync": "yellow",
    "would upgrade": "yellow",
    "would apply": "yellow",
    "skipped": "dim",
    "missing": "red",
    "failed": "red bold",
    "post-failed": "red",
}
QUIET_ACTIONS = {"up-to-date", "unchanged", "ok"}


@cache
def console() -> Console:
    """rich Console on the saved real-stdout fd (duped, owned independently of TERMINAL_FD) so is_terminal reflects the real terminal, not the log pipe."""
    if logs.TERMINAL_FD is None:
        return Console()
    return Console(file=os.fdopen(os.dup(logs.TERMINAL_FD), "w"))


def is_interactive() -> bool:
    return console().is_terminal


def _emit_log_line(line: str) -> None:
    """The pump's terminal sink: print a pumped log line through the Console so it coordinates with live regions; out() passes output verbatim, no wrap or markup."""
    console().out(line.rstrip("\n"), highlight=False)


logs.LINE_SINK = _emit_log_line


def show_table(rows: list[dict], title: str = "") -> None:
    """Render rows as a rich table plus TOON in the log file on an interactive terminal; on a non-terminal stdout, emit plain TOON to both."""
    if not rows or not is_interactive():
        log_toon(rows, note=title)
        return
    _render_table(rows, title)
    _append_toon(rows, title)


def _render_table(rows: list[dict], title: str) -> None:
    columns = list(rows[0])
    table = Table(
        title=title or None,
        box=ROUNDED,
        title_style="bold",
        header_style="bold cyan",
    )
    for column in columns:
        table.add_column(column)
    for row in rows:
        cells = [Text(str(row[column]), style=ACTION_STYLES.get(str(row[column]), "")) if column == "action" else Text(str(row[column])) for column in columns]
        quiet = str(row.get("action", "")) in QUIET_ACTIONS
        table.add_row(*cells, style="dim" if quiet else "")
    console().print(table)


def _append_toon(rows: list[dict], title: str) -> None:
    """Append rows as a TOON block to the log file (keeping it minimalist while the terminal got rich), via logs.write_log's single locked writer."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    head = f"[{stamp}] {title}\n" if title else ""
    logs.write_log(head + encode(rows) + "\n")


class ProgressHandle:
    """No-op progress handle (the non-interactive yield); the live subclass drives a rich bar, callers advance through this interface regardless of TTY."""

    def advance(self, amount: int = 1) -> None: ...


class _LiveProgress(ProgressHandle):
    def __init__(self, progress: Progress, task: TaskID) -> None:
        self._progress = progress
        self._task = task

    def advance(self, amount: int = 1) -> None:
        self._progress.advance(self._task, amount)


@contextmanager
def progress_region(description: str, total: int) -> Generator[ProgressHandle]:
    """A live, transient progress bar on an interactive terminal (cleared on exit, leaving the logs above it); a no-op handle otherwise."""
    if not is_interactive():
        yield ProgressHandle()
        return
    columns = (
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )
    with Progress(*columns, console=console(), transient=True) as progress:
        task = progress.add_task(description, total=total)
        yield _LiveProgress(progress, task)
