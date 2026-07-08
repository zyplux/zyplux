(
    """Terminal presentation: minimalist TOON in the log, rich tables/progress bars on a terminal, all """
    """routed through the one Console the pump feeds."""
)

import os
import re
from contextlib import contextmanager
from datetime import datetime
from functools import cache
from typing import TYPE_CHECKING, override

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

from totchef import logs
from totchef.logs import log_toon

if TYPE_CHECKING:
    from collections.abc import Generator

ACTION_STYLES = {
    "installed": "green",
    "upgraded": "green",
    "applied": "green",
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

LOG_LINE = re.compile(r"^\[([^\]]+)\] (\S+)\s+(\w+)\s+(.*)$", re.DOTALL)

# Distinct hues for the runner column so each cook keeps one color across its
# interleaved lines; severity stays in the message, so red/yellow/green are left
# out here to avoid reading a runner's color as a status.
RUNNER_PALETTE = (
    "cyan",
    "magenta",
    "blue",
    "bright_cyan",
    "bright_magenta",
    "bright_blue",
    "orange3",
    "purple",
    "turquoise2",
    "deep_pink3",
    "sky_blue2",
    "medium_purple",
    "dodger_blue2",
    "hot_pink3",
    "dark_violet",
    "light_sea_green",
    "dark_orange3",
    "slate_blue1",
)


@cache
def _pump_console() -> Console:
    (
        """rich Console on the saved real-stdout fd, independent of the log pipe, so is_terminal reflects the """
        """real terminal. Cached: the dup happens once."""
    )
    terminal_fd = logs.log_state.terminal
    if terminal_fd is None:
        msg = "_pump_console requires a running pump; reach it through console()"
        raise RuntimeError(msg)
    return Console(file=os.fdopen(os.dup(terminal_fd), "w"))


def console() -> Console:
    (
        """The presentation console: the cached terminal-fd console with a pump running, else a fresh Console """
        """on live stdout tracking the environment per call."""
    )
    if logs.log_state.terminal is None:
        return Console()
    return _pump_console()


def is_interactive() -> bool:
    return console().is_terminal


def _line_style(level: str, message: str) -> str:
    (
        """The color for a terminal log line, chosen by severity then by what it announces: errors red, """
        """warnings yellow, starting bluish, success green."""
    )
    if level in {"ERROR", "CRITICAL"}:
        return "bold red"
    if level == "WARNING":
        return "bold yellow"
    if message.startswith("started"):
        return "cornflower_blue"
    if message.startswith("completed"):
        return "green3"
    return ""


_runner_colors: dict[str, str] = {}


def _runner_style(runner: str) -> str:
    (
        """A stable color for a cook's name, assigned from the palette in first-seen order so cooks running """
        """together are always distinct hues."""
    )
    if runner not in _runner_colors:
        _runner_colors[runner] = RUNNER_PALETTE[len(_runner_colors) % len(RUNNER_PALETTE)]
    return _runner_colors[runner]


def _colorize_log_line(line: str) -> Text:
    (
        """Restyle a pumped log line for the terminal: drop the level column, dim the timestamp, color the """
        """runner, tint the message; unrecognized stays plain."""
    )
    match = LOG_LINE.match(line)
    if match is None:
        return Text(line)
    timestamp, runner, level, message = match.groups()
    runner_style = _runner_style(runner)
    text = Text()
    text.append(f"[{timestamp}] ", style=runner_style)
    text.append(f"{runner: <28} ", style=runner_style)
    text.append(message, style=_line_style(level, message))
    return text


def _emit_log_line(line: str) -> None:
    (
        """The pump's terminal sink: print a pumped log line through the Console so it coordinates with live """
        """regions; soft_wrap keeps lines unbroken."""
    )
    console().print(_colorize_log_line(line.rstrip("\n")), soft_wrap=True)


logs.LINE_SINK = _emit_log_line


def show_table(rows: list[dict[str, str]], title: str = "", summary: list[dict[str, str]] | None = None) -> None:
    (
        """Render rows as a rich table plus TOON in the log on an interactive terminal, plain TOON otherwise; """
        """`summary` rows close under a divider."""
    )
    summary = summary or []
    if not rows or not is_interactive():
        log_toon(rows + summary, note=title)
        return
    _render_table(rows, title, summary)
    _append_toon(rows + summary, title)


def _report_cell(column: str, value: str, action: str) -> Text:
    (
        """Style one report cell as a diff: `action`/`latest` get the verb's color, `current` stays plain, """
        """`before` dims; identity carries its cook's color."""
    )
    if column == "action":
        return Text(value, style=ACTION_STYLES.get(value, ""))
    if column == "latest":
        return Text(value, style=ACTION_STYLES.get(action, ""))
    if column == "before":
        return Text(value, style="dim")
    if column == "cook-node":
        return Text(value, style=_runner_style(value))
    return Text(value)


def _render_table(rows: list[dict[str, str]], title: str, summary: list[dict[str, str]]) -> None:
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
        action = row.get("action", "")
        cells = [_report_cell(column, row[column], action) for column in columns]
        quiet = action in QUIET_ACTIONS
        table.add_row(*cells, style="dim" if quiet else "")
    if summary:
        table.add_section()
        for row in summary:
            table.add_row(*(Text(row.get(column, "")) for column in columns), style="dim")
    console().print(table)


def _append_toon(rows: list[dict[str, str]], title: str) -> None:
    (
        """Append rows as a TOON block to the log file (keeping it minimalist while the terminal got rich), """
        """via logs.write_log's single locked writer."""
    )
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    head = f"[{stamp}] {title}\n" if title else ""
    logs.write_log(head + encode(rows) + "\n")


class ProgressHandle:
    (
        """No-op progress handle (the non-interactive yield); the live subclass drives a rich bar, callers """
        """advance through this interface regardless of TTY."""
    )

    def advance(self, amount: int = 1) -> None: ...


class _LiveProgress(ProgressHandle):
    def __init__(self, progress: Progress, task: TaskID) -> None:
        self._progress = progress
        self._task = task

    @override
    def advance(self, amount: int = 1) -> None:
        self._progress.advance(self._task, amount)


@contextmanager
def progress_region(description: str, total: int) -> Generator[ProgressHandle]:
    (
        """A live, transient progress bar on an interactive terminal (cleared on exit, leaving the logs above """
        """it); a no-op handle otherwise."""
    )
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
