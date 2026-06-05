#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["psutil>=7", "rich>=14", "typer>=0.16"]
# ///
"""Live top-like CPU view of the VS Code process trees, each process labeled by role or owning extension. Installed verbatim to ~/.local/bin; uv resolves the inline dependencies on first run."""

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import psutil
import typer
from rich.console import Console, Group
from rich.filesize import decimal as format_filesize
from rich.live import Live
from rich.table import Column, Table
from rich.text import Text

__version__ = "0.1.0"

VSCODE_PROCESS_NAMES = {"code", "code-insiders", "code-oss"}
EXTHOST_NODE_FLAGS = ("--inspect-port", "--dns-result-order")
EXTENSION_DIR_PATTERN = re.compile(r"/extensions/([^/]+)/")
EXTENSION_VERSION_SUFFIX = re.compile(r"-\d+\.\d+\.\d+\S*$")
BUILTIN_EXTENSIONS_PATH = "/resources/app/extensions/"
CHROMIUM_ROLE_NAMES = {"renderer": "window", "gpu-process": "gpu"}
BUSY_CPU_PERCENT = 50
IDLE_CPU_PERCENT = 0.5
CPU_TIER_STYLES = ((BUSY_CPU_PERCENT, "bold red"), (20, "yellow"), (IDLE_CPU_PERCENT, "green"))
HEADER_AND_FOOTER_LINES = 5

console = Console(highlight=False)
app = typer.Typer(add_completion=False)


@dataclass(slots=True)
class ProcessRow:
    pid: int
    variant: str
    role: str
    cpu_percent: float
    rss_bytes: int


def find_chromium_type(cmdline: list[str]) -> str | None:
    return next((arg.removeprefix("--type=") for arg in cmdline if arg.startswith("--type=")), None)


def describe_script(cmdline: list[str], process_name: str) -> str:
    for arg in cmdline[1:]:
        if "/" in arg and not arg.startswith("-"):
            return "/".join(Path(arg).parts[-2:])
    return process_name


def label_role(cmdline: list[str], process_name: str, is_main: bool) -> str:
    joined = " ".join(cmdline)
    match find_chromium_type(cmdline):
        case "utility" if "node.mojom.NodeService" in joined:
            is_exthost = any(arg.startswith(EXTHOST_NODE_FLAGS) for arg in cmdline)
            return "extension host" if is_exthost else "node service"
        case "utility" if "network.mojom.NetworkService" in joined:
            return "network service"
        case str() as chromium_type:
            return CHROMIUM_ROLE_NAMES.get(chromium_type, chromium_type)
        case None if is_main:
            return "main"
        case None if extension_dir := EXTENSION_DIR_PATTERN.search(joined):
            prefix = "builtin:" if BUILTIN_EXTENSIONS_PATH in joined else "ext:"
            return prefix + EXTENSION_VERSION_SUFFIX.sub("", extension_dir.group(1))
        case None if process_name in VSCODE_PROCESS_NAMES:
            return describe_script(cmdline, process_name)
        case _:
            return process_name


def find_main_processes() -> list[psutil.Process]:
    mains: list[psutil.Process] = []
    for proc in psutil.process_iter(["name", "ppid"]):
        if proc.info["name"] not in VSCODE_PROCESS_NAMES:
            continue
        try:
            parent_name = psutil.Process(proc.info["ppid"]).name()
        except psutil.Error:
            parent_name = ""
        if parent_name not in VSCODE_PROCESS_NAMES:
            mains.append(proc)
    return mains


def sample_processes(tracked: dict[int, psutil.Process]) -> list[ProcessRow]:
    rows: list[ProcessRow] = []
    live_pids: set[int] = set()
    for main in find_main_processes():
        variant = main.info["name"].removeprefix("code-")
        try:
            subtree = [main, *main.children(recursive=True)]
        except psutil.Error:
            continue
        for proc in subtree:
            if proc.pid in live_pids:
                continue
            live_pids.add(proc.pid)
            sampler = tracked.setdefault(proc.pid, proc)
            try:
                with sampler.oneshot():
                    cpu_percent = sampler.cpu_percent()
                    rss_bytes = sampler.memory_info().rss
                    cmdline = sampler.cmdline()
                    process_name = sampler.name()
            except psutil.Error:
                continue
            role = label_role(cmdline, process_name, is_main=proc.pid == main.pid)
            rows.append(ProcessRow(proc.pid, variant, role, cpu_percent, rss_bytes))
    for stale_pid in set(tracked) - live_pids:
        del tracked[stale_pid]
    return sorted(rows, key=lambda row: (row.cpu_percent, row.rss_bytes), reverse=True)


def get_cpu_style(cpu_percent: float) -> str:
    return next((style for threshold, style in CPU_TIER_STYLES if cpu_percent >= threshold), "dim")


def get_role_style(role: str) -> str:
    if role.startswith("ext:"):
        return "cyan"
    if role.startswith("builtin:"):
        return "bright_blue"
    if role == "extension host":
        return "magenta"
    return ""


def get_row_style(cpu_percent: float) -> str:
    if cpu_percent > BUSY_CPU_PERCENT:
        return "bold red"
    return "" if cpu_percent >= IDLE_CPU_PERCENT else "dim"


def build_view(rows: list[ProcessRow], visible_count: int | None) -> Group:
    total_cpu = sum(row.cpu_percent for row in rows)
    header = Text.assemble(
        ("ctop", "bold cyan"),
        (f" · {time.strftime('%H:%M:%S')} · {len(rows)} processes · ", ""),
        (f"{total_cpu:.0f}% cpu", get_cpu_style(total_cpu)),
    )
    if not rows:
        return Group(header, Text("no VS Code processes found", style="dim"))
    table = Table(
        Column("pid", justify="right"),
        Column("cpu%", justify="right", header_style="bold reverse"),
        Column("rss", justify="right"),
        "variant",
        Column("process", ratio=1),
        box=None,
        pad_edge=False,
        expand=True,
        header_style="reverse",
    )
    visible = rows if visible_count is None else rows[:visible_count]
    for row in visible:
        row_style = get_row_style(row.cpu_percent)
        cpu_cell = Text(f"{row.cpu_percent:.1f}", style=row_style or get_cpu_style(row.cpu_percent))
        role_cell = Text(row.role, style=row_style or get_role_style(row.role))
        table.add_row(str(row.pid), cpu_cell, format_filesize(row.rss_bytes), row.variant, role_cell, style=row_style)
    hidden_count = len(rows) - len(visible)
    footer = Text(f"… {hidden_count} quieter processes", style="dim") if hidden_count else Text("ctrl+c quits", style="dim")
    return Group(header, table, footer)


def get_visible_row_capacity() -> int:
    return max(console.size.height - HEADER_AND_FOOTER_LINES, 5)


@app.command()
def main(
    interval: Annotated[float, typer.Option("--interval", "-d", min=0.1, help="seconds between refreshes")] = 2.0,
    once: Annotated[bool, typer.Option("--once", help="print one snapshot and exit")] = False,
    version: Annotated[bool, typer.Option("--version", help="print version and exit")] = False,
) -> None:
    """Live top-like CPU view of the VS Code process trees, each process labeled by role or owning extension."""
    if version:
        console.print(__version__)
        return
    tracked: dict[int, psutil.Process] = {}
    try:
        sample_processes(tracked)
        time.sleep(interval)
        if once or not console.is_terminal:
            console.print(build_view(sample_processes(tracked), visible_count=None))
            return
        with Live(console=console, screen=True, auto_refresh=False) as live:
            while True:
                live.update(build_view(sample_processes(tracked), get_visible_row_capacity()), refresh=True)
                time.sleep(interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    app()
