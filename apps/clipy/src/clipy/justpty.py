#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["typer>=0.26.8"]
# ///
"""Run a `just` recipe under a PTY, teeing output to the terminal and an ANSI-free transcript to a per-run log.

Each run writes `logs/just-<timestamp>-<pid>.log` (announced on stderr as `» log: …`), repoints the
`logs/just.log` symlink at it, and prunes all but the newest KEPT_RUN_LOGS run logs. The transcript is
cleaned as it streams, so it is greppable while the run is still going.

Installed as `justpty` (to ~/.local/bin, via totchef) or invoked as `./just` inside this repo — a symlink
to this file; either way it wraps whatever `just` it finds on PATH under the invoking directory, and logs
land under that directory's `logs/`.
"""

from __future__ import annotations

import codecs
import os
import pty
import select
import shlex
import shutil
import signal
import sys
import termios
import time
import tty
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import FrameType
    from typing import Literal, TextIO

__version__ = "0.1.0"

STDIN_FD = 0
STDOUT_FD = 1
PTY_READ_BYTES = 65536
KEPT_RUN_LOGS = 20
HEADLESS_WINSIZE = (50, 200)
SIGNAL_EXIT_BASE = 128
JUST_MISSING_EXIT = 127
CSI_FINAL_MIN = "@"
CSI_FINAL_MAX = "~"
ASCII_DEL = "\x7f"
CURSOR_MOTION_FINALS = "ABEFHJSTfd"

type ParserState = Literal["text", "esc", "csi", "osc", "osc_esc", "charset"]

app = typer.Typer(add_completion=False)


class TranscriptCleaner:
    """Renders a PTY byte stream as plain text, replaying CR/backspace/erase overwrites within each line."""

    def __init__(self) -> None:
        self._decode = codecs.getincrementaldecoder("utf-8")(errors="replace").decode
        self._state: ParserState = "text"
        self._csi_params = ""
        self._line: list[str] = []
        self._col = 0

    def feed(self, chunk: bytes) -> str:
        return "".join(self._consume(ch) for ch in self._decode(chunk))

    def flush(self) -> str:
        return self._take_line() if self._line else ""

    def _consume(self, ch: str) -> str:
        match self._state:
            case "text":
                return self._consume_text(ch)
            case "csi":
                return self._consume_csi(ch)
            case "esc":
                self._consume_esc(ch)
            case "osc" | "osc_esc":
                self._consume_osc(ch)
            case "charset":
                self._state = "text"
        return ""

    def _consume_text(self, ch: str) -> str:
        if ch == "\x1b":
            self._state = "esc"
        elif ch == "\n":
            return self._take_line()
        elif ch == "\r":
            self._col = 0
        elif ch == "\b":
            self._col = max(self._col - 1, 0)
        elif ch == "\t" or (ch >= " " and ch != ASCII_DEL):
            self._put(ch)
        return ""

    def _consume_esc(self, ch: str) -> None:
        if ch == "[":
            self._state = "csi"
            self._csi_params = ""
        elif ch == "]":
            self._state = "osc"
        elif ch in "()#%":
            self._state = "charset"
        else:
            self._state = "text"

    def _consume_csi(self, ch: str) -> str:
        if CSI_FINAL_MIN <= ch <= CSI_FINAL_MAX:
            self._state = "text"
            return self._apply_csi(ch)
        self._csi_params += ch
        return ""

    def _consume_osc(self, ch: str) -> None:
        if self._state == "osc_esc":
            self._state = "text" if ch == "\\" else "osc"
        elif ch == "\x07":
            self._state = "text"
        elif ch == "\x1b":
            self._state = "osc_esc"

    def _apply_csi(self, final: str) -> str:
        step = self._first_csi_param(default=1)
        if final == "K":
            self._erase_line()
        elif final == "G":
            self._col = max(step - 1, 0)
        elif final == "C":
            self._col += step
        elif final == "D":
            self._col = max(self._col - step, 0)
        elif final in CURSOR_MOTION_FINALS and self._line:
            return self._take_line()
        return ""

    def _erase_line(self) -> None:
        match self._first_csi_param(default=0):
            case 0:
                del self._line[self._col :]
            case 1:
                blank_span = min(self._col + 1, len(self._line))
                self._line[:blank_span] = [" "] * blank_span
            case _:
                self._line.clear()

    def _first_csi_param(self, default: int) -> int:
        head = self._csi_params.split(";")[0].lstrip("?>=!<")
        return int(head) if head.isdigit() else default

    def _put(self, ch: str) -> None:
        if self._col < len(self._line):
            self._line[self._col] = ch
        else:
            self._line.extend([" "] * (self._col - len(self._line)))
            self._line.append(ch)
        self._col += 1

    def _take_line(self) -> str:
        text = "".join(self._line).rstrip()
        self._line.clear()
        self._col = 0
        return text + "\n"


def write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


def read_pty(master_fd: int) -> bytes:
    """A PTY master raises EIO once the child exits; treat any read failure as end of stream."""
    try:
        return os.read(master_fd, PTY_READ_BYTES)
    except OSError:
        return b""


def forward_stdin(master_fd: int) -> bool:
    try:
        chunk = os.read(STDIN_FD, PTY_READ_BYTES)
    except OSError:
        return False
    if not chunk:
        return False
    write_all(master_fd, chunk)
    return True


def watchable(fd: int) -> bool:
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True


def relay(master_fd: int, log: TextIO) -> None:
    cleaner = TranscriptCleaner()
    mirror_raw = os.isatty(STDOUT_FD)
    watched = [fd for fd in (master_fd, STDIN_FD) if watchable(fd)]

    def emit(chunk: bytes) -> bool:
        cleaned = cleaner.feed(chunk) if chunk else cleaner.flush()
        log.write(cleaned)
        with suppress(OSError):
            if mirror_raw:
                if chunk:
                    write_all(STDOUT_FD, chunk)
            elif cleaned:
                write_all(STDOUT_FD, cleaned.encode())
        return bool(chunk)

    while True:
        readable = select.select(watched, [], [])[0]
        if STDIN_FD in readable and not forward_stdin(master_fd):
            watched.remove(STDIN_FD)
        if master_fd in readable and not emit(read_pty(master_fd)):
            return


def spawn_just(just_binary: str, recipe_args: list[str]) -> tuple[int, int]:
    child_pid, master_fd = pty.fork()
    if child_pid == pty.CHILD:
        os.execv(just_binary, ["just", *recipe_args])
    return child_pid, master_fd


def copy_winsize(master_fd: int) -> None:
    with suppress(OSError, termios.error):
        if os.isatty(STDOUT_FD):
            termios.tcsetwinsize(master_fd, termios.tcgetwinsize(STDOUT_FD))
        else:
            termios.tcsetwinsize(master_fd, HEADLESS_WINSIZE)


def forward_signals(child_pid: int, master_fd: int) -> None:
    def deliver(signum: int, _frame: FrameType | None) -> None:
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(child_pid, signum)

    def resize(_signum: int, _frame: FrameType | None) -> None:
        copy_winsize(master_fd)

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, deliver)
    signal.signal(signal.SIGWINCH, resize)


@contextmanager
def raw_stdin() -> Generator[None]:
    if not os.isatty(STDIN_FD):
        yield
        return
    saved = termios.tcgetattr(STDIN_FD)
    tty.setraw(STDIN_FD)
    try:
        yield
    finally:
        termios.tcsetattr(STDIN_FD, termios.TCSADRAIN, saved)


def run_under_pty(just_binary: str, recipe_args: list[str], log: TextIO) -> int:
    child_pid, master_fd = spawn_just(just_binary, recipe_args)
    copy_winsize(master_fd)
    forward_signals(child_pid, master_fd)
    try:
        with raw_stdin():
            relay(master_fd, log)
    finally:
        os.close(master_fd)
    exit_code = os.waitstatus_to_exitcode(os.waitpid(child_pid, 0)[1])
    return exit_code if exit_code >= 0 else SIGNAL_EXIT_BASE - exit_code


def link_latest(logs_dir: Path, run_log_path: Path) -> None:
    staging = logs_dir / f".just.log.{os.getpid()}"
    staging.unlink(missing_ok=True)
    staging.symlink_to(run_log_path.name)
    staging.replace(logs_dir / "just.log")


def prune_stale_logs(logs_dir: Path) -> None:
    for stale in sorted(logs_dir.glob("just-*.log"))[:-KEPT_RUN_LOGS]:
        stale.unlink(missing_ok=True)


def scrub_uv_script_venv() -> None:
    """`uv run --script` exports VIRTUAL_ENV for the wrapper's own environment; recipes must not inherit it."""
    if os.environ.get("VIRTUAL_ENV") == sys.prefix:
        del os.environ["VIRTUAL_ENV"]


def run_just(recipe_args: list[str]) -> int:
    scrub_uv_script_venv()
    just_binary = shutil.which("just")
    if just_binary is None:
        sys.stderr.write("just not found on PATH\n")
        return JUST_MISSING_EXIT
    working_dir = Path.cwd()
    logs_dir = working_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    started = datetime.now(tz=UTC).astimezone()
    run_log_path = logs_dir / f"just-{started:%Y%m%d-%H%M%S}-{os.getpid()}.log"
    sys.stderr.write(f"» log: {run_log_path.relative_to(working_dir)}\n")
    begun = time.monotonic()
    with run_log_path.open("w", buffering=1, encoding="utf-8") as log:
        log.write(f"=== {started.isoformat(timespec='seconds')} | {shlex.join(['just', *recipe_args])}\n")
        link_latest(logs_dir, run_log_path)
        status = run_under_pty(just_binary, recipe_args, log)
        ended = datetime.now(tz=UTC).astimezone()
        log.write(f"=== exit {status} | {ended.isoformat(timespec='seconds')} | {time.monotonic() - begun:.1f}s\n")
    prune_stale_logs(logs_dir)
    return status


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def main(
    ctx: typer.Context,
    *,
    version: Annotated[bool, typer.Option("--version", help="print version and exit")] = False,
) -> None:
    """Run a `just` recipe under a PTY, teeing output to the terminal and a per-run log."""
    if version:
        typer.echo(__version__)
        return
    raise typer.Exit(run_just(ctx.args))


if __name__ == "__main__":
    app()
