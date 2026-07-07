#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["psutil>=7", "rich>=14", "typer>=0.16", "websockets>=14"]
# ///
"""Live top-like CPU view of the VS Code process trees, each process labeled by role or owning extension. Installed verbatim to ~/.local/bin; uv resolves the inline dependencies on first run."""

import json
import os
import re
import select
import sys
import termios
import time
import tty
import urllib.request
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import psutil
import typer
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect
from rich.console import Console, Group
from rich.filesize import decimal as format_filesize
from rich.live import Live
from rich.table import Column, Table
from rich.text import Text

__version__ = "0.2.1"

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

INSPECTOR_LOCALHOSTS = ("127.0.0.1", "::1")
INSPECTOR_PROBE_TIMEOUT_SECONDS = 0.5
VSCODE_CORE_PATH = "/resources/app/"
PROFILE_MIN_CPU_PERCENT = 10.0
PROFILE_SAMPLE_SECONDS = 1.5
PROFILE_SAMPLING_INTERVAL_US = 500
PROFILE_RECV_TIMEOUT_SECONDS = 10.0
PROFILE_MIN_SHARE_PERCENT = 1.0
PROFILE_MAX_SUBROWS = 8

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


def list_inspector_addresses(pid: int) -> list[tuple[str, int]]:
    try:
        connections = psutil.Process(pid).net_connections(kind="inet")
    except psutil.Error:
        return []
    return [
        (conn.laddr.ip, conn.laddr.port) for conn in connections if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.ip in INSPECTOR_LOCALHOSTS
    ]


def find_inspector_websocket(pid: int) -> str | None:
    for ip, port in list_inspector_addresses(pid):
        host = f"[{ip}]" if ":" in ip else ip
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/json/list", timeout=INSPECTOR_PROBE_TIMEOUT_SECONDS) as response:
                targets = json.load(response)
        except OSError, ValueError:
            continue
        for target in targets:
            if websocket_url := target.get("webSocketDebuggerUrl"):
                return websocket_url
    return None


def sample_exthost_profile(websocket_url: str, seconds: float) -> dict | None:
    try:
        with connect(websocket_url, max_size=None, open_timeout=2) as inspector:
            request_id = 0

            def call(method: str, params: dict | None = None) -> dict | None:
                nonlocal request_id
                request_id += 1
                pending = request_id
                inspector.send(json.dumps({"id": pending, "method": method, "params": params or {}}))
                while True:
                    message = json.loads(inspector.recv(timeout=PROFILE_RECV_TIMEOUT_SECONDS))
                    if message.get("id") == pending:
                        return message.get("result")

            call("Profiler.enable")
            call("Profiler.setSamplingInterval", {"interval": PROFILE_SAMPLING_INTERVAL_US})
            call("Profiler.start")
            time.sleep(seconds)
            result = call("Profiler.stop")
    except OSError, ValueError, TimeoutError, WebSocketException:
        return None
    return result.get("profile") if result else None


def attribute_profile(profile: dict) -> list[tuple[str, float]]:
    self_ticks: Counter[str] = Counter()
    for node in profile.get("nodes", []):
        url = node["callFrame"].get("url", "")
        if extension_dir := EXTENSION_DIR_PATTERN.search(url):
            prefix = "builtin:" if BUILTIN_EXTENSIONS_PATH in url else "ext:"
            owner = prefix + EXTENSION_VERSION_SUFFIX.sub("", extension_dir.group(1))
        elif VSCODE_CORE_PATH in url:
            owner = "vscode-core"
        else:
            owner = "native/gc"
        self_ticks[owner] += node.get("hitCount", 0)
    total_ticks = sum(self_ticks.values()) or 1
    return [(owner, 100 * ticks / total_ticks) for owner, ticks in self_ticks.most_common()]


def profile_busy_exthosts(rows: list[ProcessRow]) -> dict[int, list[tuple[str, float]]]:
    attribution: dict[int, list[tuple[str, float]]] = {}
    for row in rows:
        if row.role != "extension host" or row.cpu_percent < PROFILE_MIN_CPU_PERCENT:
            continue
        websocket_url = find_inspector_websocket(row.pid)
        if websocket_url is None:
            continue
        profile = sample_exthost_profile(websocket_url, PROFILE_SAMPLE_SECONDS)
        if profile:
            attribution[row.pid] = attribute_profile(profile)
    return attribution


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


def build_view(
    rows: list[ProcessRow],
    visible_count: int | None,
    attribution: dict[int, list[tuple[str, float]]] | None = None,
    profiling: bool = False,
    interactive: bool = False,
) -> Group:
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
        owners = [(owner, share) for owner, share in (attribution or {}).get(row.pid, []) if share >= PROFILE_MIN_SHARE_PERCENT]
        for owner, share in owners[:PROFILE_MAX_SUBROWS]:
            owner_style = get_role_style(owner) or "dim"
            contribution = Text(f"{row.cpu_percent * share / 100:.1f}", style=owner_style)
            table.add_row("", contribution, "", "", Text(f"  └ {owner}", style=owner_style))
    if not interactive:
        state = None
    elif not profiling:
        state = "profiling off"
    elif attribution is None:
        state = "profiling…"
    else:
        state = "profiling on"
    hint = f"p {state} · q quit" if state else "ctrl+c quits"
    hidden_count = len(rows) - len(visible)
    if hidden_count:
        hint = f"… {hidden_count} quieter · {hint}"
    return Group(header, table, Text(hint, style="dim"))


def get_visible_row_capacity() -> int:
    return max(console.size.height - HEADER_AND_FOOTER_LINES, 5)


@contextmanager
def raw_keyboard():
    if not sys.stdin.isatty():
        yield
        return
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def read_key(timeout: float) -> str | None:
    if not sys.stdin.isatty():
        time.sleep(timeout)
        return None
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return None
    return os.read(sys.stdin.fileno(), 1).decode("utf-8", "ignore")


@app.command()
def main(
    interval: Annotated[float, typer.Option("--interval", "-d", min=0.1, help="seconds between refreshes")] = 2.0,
    once: Annotated[bool, typer.Option("--once", help="print one snapshot and exit")] = False,
    profile_exthost: Annotated[
        bool,
        typer.Option("--profile-exthost", help="attach to busy extension hosts and attribute their CPU to the owning extension"),
    ] = False,
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
            rows = sample_processes(tracked)
            attribution = profile_busy_exthosts(rows) if profile_exthost else None
            console.print(build_view(rows, visible_count=None, attribution=attribution))
            return
        profiling = profile_exthost
        with raw_keyboard(), Live(console=console, screen=True, auto_refresh=False) as live:
            while True:
                rows = sample_processes(tracked)
                attribution = None
                if profiling:
                    live.update(build_view(rows, get_visible_row_capacity(), None, profiling=True, interactive=True), refresh=True)
                    attribution = profile_busy_exthosts(rows)
                live.update(build_view(rows, get_visible_row_capacity(), attribution, profiling=profiling, interactive=True), refresh=True)
                key = read_key(interval)
                if key in ("q", "Q"):
                    break
                if key in ("p", "P"):
                    profiling = not profiling
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    app()
