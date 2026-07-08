"""Logging core: log pump (one thread owns file+terminal, no live-region interleave), drain barrier, loguru config."""

import os
import pwd
import sys
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from loguru import logger
from toon_format import encode

from totchef.log_pump import emit_terminal, pump_lines

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping, Sequence


def log_dir() -> Path:
    """Per-run logs under XDG state dir, resolved from SUDO_USER so root re-exec writes to the user's home."""
    sudo_user = os.environ.get("SUDO_USER")
    home = Path(pwd.getpwnam(sudo_user).pw_dir) if sudo_user else Path.home()
    state = Path(os.environ["XDG_STATE_HOME"]) if os.environ.get("XDG_STATE_HOME") else home / ".local" / "state"
    return state / "totchef" / "logs"


# The runner column names who is speaking: "chef" for the orchestrator's own
# lines, the node id (e.g. url.bun, apt_pkg) while a cook runs — see cook_context.
# Width fits the longest node id so the level/message columns stay aligned.
DEFAULT_RUNNER = Path(sys.argv[0]).stem

LOG_FORMAT = "[{time:YYYY-MM-DD HH:mm:ss}] {extra[runner]: <28} {level: <7} {message}"

SHARED_LOG_ENV = "TOTCHEF_LOG_FILE"

# Inline mode: run every cook in this process (no fork, no sudo) and stream logs
# straight to the live stderr instead of through the fd-pump. A foreground/debug
# run, and the seam the story tests drive totchef through their public CLI on.
INLINE_ENV = "TOTCHEF_INLINE"


def inline_mode() -> bool:
    return bool(os.environ.get(INLINE_ENV))


class _LogState:
    """Pump state, mutated in place: terminal is a stdout dup, pipe_write feeds drain_logs, log_handle the log file."""

    terminal: int | None = None
    pipe_write: int | None = None
    log_handle: TextIO | None = None
    echo_to_terminal: bool = True


log_state = _LogState()

# The log pump: one parent thread reads the merged stdout/stderr of the parent and
# every forked cook off the pipe, then mirrors each line to the log file (under
# LOG_LOCK) and the terminal (via LINE_SINK). One reader => the terminal has exactly
# one writer, so a live region (table / progress bar) never interleaves with logs.
LOG_LOCK = threading.Lock()
DRAIN_EVENTS: dict[str, threading.Event] = {}

# terminal.py registers a sink that routes pumped lines through its rich Console
# (so they coordinate with live regions). Kept as a hook to avoid a logs ->
# terminal import cycle.
LINE_SINK: Callable[[str], None] | None = None

# Configured at import so pre-sudo messages get timestamped too.
logger.remove()
logger.configure(extra={"runner": DEFAULT_RUNNER})
logger.add(sys.stderr, format=LOG_FORMAT, level="INFO", colorize=False)


@contextmanager
def cook_context(runner: str) -> Generator[None]:
    """Label log lines with the cook's node id, then restore "chef"; logger.configure reaches worker threads too."""
    logger.configure(extra={"runner": runner})
    try:
        yield
    finally:
        logger.configure(extra={"runner": DEFAULT_RUNNER})


def write_log(text: str) -> None:
    """Append text to the run's log file under a lock — the only writer shared by the pump thread and TOON writer."""
    if log_state.log_handle is None:
        return
    with LOG_LOCK:
        log_state.log_handle.write(text)
        log_state.log_handle.flush()


def set_terminal_echo(*, enabled: bool) -> None:
    """Toggle whether the pump mirrors log lines to the terminal; the log file is written either way."""
    log_state.echo_to_terminal = enabled


def _emit_terminal(line: str) -> None:
    emit_terminal(line, enabled=log_state.echo_to_terminal, sink=LINE_SINK)


def _pump(read_fd: int) -> None:
    """Mirror each line to file and terminal; a line matching a drain marker is swallowed and signals its event."""
    with os.fdopen(read_fd, "r", errors="replace") as stream:
        pump_lines(stream, write_log=write_log, emit_terminal=_emit_terminal, drain_events=DRAIN_EVENTS)


def drain_logs(timeout: float = 5.0) -> None:
    """FIFO barrier: block until the pump drains what's written so far; call only once all forked cooks are reaped."""
    if log_state.pipe_write is None:
        return
    marker = uuid.uuid4().hex
    DRAIN_EVENTS[marker] = event = threading.Event()
    os.write(log_state.pipe_write, f"{marker}\n".encode())
    event.wait(timeout)


def open_log_file() -> Path:
    """Resolve the run's log file (honors SHARED_LOG_ENV), create it, chown to SUDO_USER; shared by both start paths."""
    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    if existing := os.environ.get(SHARED_LOG_ENV):
        log_file = Path(existing)
    else:
        log_file = directory / f"totchef-{datetime.now().astimezone():%Y%m%d-%H%M%S}.log"
        os.environ[SHARED_LOG_ENV] = str(log_file)
    log_file.touch(exist_ok=True)
    if sudo_user := os.environ.get("SUDO_USER"):
        pw = pwd.getpwnam(sudo_user)
        for path in (directory.parent, directory, log_file):
            os.chown(path, pw.pw_uid, pw.pw_gid)
    return log_file


@contextmanager
def start_inline_logging() -> Generator[Path]:
    """Inline start: no fd redirect, no pump; open the log file, point loguru at stderr so logs reach the terminal."""
    log_file = open_log_file()
    with Path(log_file).open("a", encoding="utf-8") as handle:
        log_state.log_handle = handle
        logger.remove()
        logger.configure(extra={"runner": DEFAULT_RUNNER})
        logger.add(sys.stderr, format=LOG_FORMAT, level="INFO", colorize=False)
        yield log_file
    log_state.log_handle = None


@contextmanager
def start_logging(*, echo_to_terminal: bool = True) -> Generator[Path]:
    """Open logs/<run>.log, start the pump (redirect fd 1/2 to a pipe read by a thread); honors SHARED_LOG_ENV."""
    set_terminal_echo(enabled=echo_to_terminal)
    if inline_mode():
        with start_inline_logging() as log_file:
            yield log_file
        return
    log_file = open_log_file()

    if log_state.terminal is None:
        log_state.terminal = os.dup(1)

    with Path(log_file).open("a", encoding="utf-8") as handle:
        log_state.log_handle = handle

        read_fd, write_fd = os.pipe()
        log_state.pipe_write = os.dup(write_fd)
        os.dup2(write_fd, 1)
        os.dup2(write_fd, 2)
        os.close(write_fd)
        threading.Thread(target=_pump, args=(read_fd,), daemon=True).start()
        # The pump runs alongside cook_runner's forks. Quiesce the file lock across
        # fork so a child can never inherit it mid-write (cook children never touch
        # write_log or the rich Console, so those are the only locks at risk).
        os.register_at_fork(
            before=LOG_LOCK.acquire,
            after_in_parent=LOG_LOCK.release,
            after_in_child=LOG_LOCK.release,
        )
        yield log_file
    log_state.log_handle = None


def log_toon(rows: Sequence[Mapping[str, object]], note: str = "") -> None:
    """Log a list of flat dicts as a TOON table, one logger line per row line."""
    if note:
        logger.info(note)
    for line in encode(rows).splitlines():
        logger.info(line)
