"""Logging core: the log pump (one thread owns file + terminal so a live region never interleaves with logs), the FIFO drain barrier, loguru config."""

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

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping, Sequence


def log_dir() -> Path:
    """Per-run logs under the user's XDG state dir (~/.local/state/totchef/logs) — resolved from SUDO_USER so root re-exec writes to the user's home."""
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


class _PumpFds:
    """The pump's own fds, mutated in place (never rebound) so start_logging avoids `global`: terminal is stdout's dup, pipe_write feeds drain_logs."""

    terminal: int | None = None
    pipe_write: int | None = None


pump_fds = _PumpFds()

# The log pump: one parent thread reads the merged stdout/stderr of the parent and
# every forked cook off the pipe, then mirrors each line to the log file (under
# LOG_LOCK) and the terminal (via LINE_SINK). One reader => the terminal has exactly
# one writer, so a live region (table / progress bar) never interleaves with logs.
LOG_HANDLE: TextIO | None = None
LOG_LOCK = threading.Lock()
DRAIN_EVENTS: dict[str, threading.Event] = {}

# terminal.py registers a sink that routes pumped lines through its rich Console
# (so they coordinate with live regions). Kept as a hook to avoid a logs ->
# terminal import cycle.
LINE_SINK: Callable[[str], None] | None = None

# Whether the pump also mirrors log lines to the terminal. Dry-run turns this off
# so `just plan` shows only the report table; the log file still records every line.
ECHO_LOGS_TO_TERMINAL: bool = True

# Configured at import so pre-sudo messages get timestamped too.
logger.remove()
logger.configure(extra={"runner": DEFAULT_RUNNER})
logger.add(sys.stderr, format=LOG_FORMAT, level="INFO", colorize=False)


@contextmanager
def cook_context(runner: str) -> Generator[None]:
    """Label log lines while a cook runs with its node id, then restore "chef"; logger.configure (not contextualize) reaches worker threads too."""
    logger.configure(extra={"runner": runner})
    try:
        yield
    finally:
        logger.configure(extra={"runner": DEFAULT_RUNNER})


def write_log(text: str) -> None:
    """Append text to the run's log file under a lock — the only writer, shared by the pump thread and terminal.py's TOON writer."""
    if LOG_HANDLE is None:
        return
    with LOG_LOCK:
        LOG_HANDLE.write(text)
        LOG_HANDLE.flush()


def set_terminal_echo(enabled: bool) -> None:
    """Toggle whether the pump mirrors log lines to the terminal; the log file is written either way."""
    global ECHO_LOGS_TO_TERMINAL
    ECHO_LOGS_TO_TERMINAL = enabled


def _emit_terminal(line: str) -> None:
    if ECHO_LOGS_TO_TERMINAL and LINE_SINK is not None:
        LINE_SINK(line)


def _pump(read_fd: int) -> None:
    """Mirror each line of the merged log stream to the file and terminal; a line matching a registered drain marker is swallowed and signals its event."""
    with os.fdopen(read_fd, "r", errors="replace") as stream:
        for line in stream:
            if (event := DRAIN_EVENTS.pop(line.strip(), None)) is not None:
                event.set()
                continue
            write_log(line)
            _emit_terminal(line)


def drain_logs(timeout: float = 5.0) -> None:
    """FIFO barrier: block until the pump drains everything written so far; call only once all forked cooks are reaped."""
    if pump_fds.pipe_write is None:
        return
    marker = uuid.uuid4().hex
    DRAIN_EVENTS[marker] = event = threading.Event()
    os.write(pump_fds.pipe_write, f"{marker}\n".encode())
    event.wait(timeout)


def open_log_file() -> Path:
    """Resolve the run's log file under the state dir (honoring SHARED_LOG_ENV), create it, chown it to SUDO_USER; shared by pumped and inline starts."""
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


def start_inline_logging() -> Path:
    """Inline start: no fd redirect, no pump. Open the log file, re-point loguru at live stderr so logs scroll to the terminal (and get captured by callers)."""
    global LOG_HANDLE
    log_file = open_log_file()
    LOG_HANDLE = Path(log_file).open("a", encoding="utf-8")
    logger.remove()
    logger.configure(extra={"runner": DEFAULT_RUNNER})
    logger.add(sys.stderr, format=LOG_FORMAT, level="INFO", colorize=False)
    return log_file


def start_logging(*, echo_to_terminal: bool = True) -> Path:
    """Open logs/<run>.log and start the pump (redirect fd 1/2 into a pipe a thread reads); honor SHARED_LOG_ENV or create a file, chowned to SUDO_USER."""
    set_terminal_echo(echo_to_terminal)
    if inline_mode():
        return start_inline_logging()
    log_file = open_log_file()

    global LOG_HANDLE
    if pump_fds.terminal is None:
        pump_fds.terminal = os.dup(1)
    LOG_HANDLE = Path(log_file).open("a", encoding="utf-8")

    read_fd, write_fd = os.pipe()
    pump_fds.pipe_write = os.dup(write_fd)
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
    return log_file


def log_toon(rows: Sequence[Mapping[str, object]], note: str = "") -> None:
    """Log a list of flat dicts as a TOON table, one logger line per row line."""
    if note:
        logger.info(note)
    for line in encode(rows).splitlines():
        logger.info(line)
