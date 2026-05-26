"""Logging core: the log pump (one thread owns the file + terminal so a live region never interleaves with log lines), the FIFO drain barrier, loguru config, and TOON logging."""

import os
import pwd
import sys
import threading
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TextIO

from loguru import logger
from toon_format import encode

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs"

# The runner column names who is speaking: "chef" for the orchestrator's own
# lines, the node id (e.g. url.bun, apt_pkg) while a cook runs — see cook_context.
# Width fits the longest node id so the level/message columns stay aligned.
DEFAULT_RUNNER = Path(sys.argv[0]).stem

LOG_FORMAT = "[{time:YYYY-MM-DD HH:mm:ss}] {extra[runner]: <28} {level: <7} {message}"

SHARED_LOG_ENV = "SYS_CONF_PY_LOG_FILE"

# A dup of the real stdout, saved before start_logging redirects fd 1/2 into the
# log pipe. terminal.py renders rich tables/progress bars here so they reach the
# human terminal without landing in the TOON log file.
TERMINAL_FD: int | None = None

# The log pump: one parent thread reads the merged stdout/stderr of the parent and
# every forked cook off the pipe, then mirrors each line to the log file (under
# LOG_LOCK) and the terminal (via LINE_SINK). One reader => the terminal has exactly
# one writer, so a live region (table / progress bar) never interleaves with logs.
LOG_HANDLE: TextIO | None = None
LOG_LOCK = threading.Lock()
LOG_PIPE_WRITE: int | None = None
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
    """Label log lines emitted while a cook runs with its node id, then restore "chef"; uses logger.configure (core extra, not contextualize) so the label reaches spawned worker threads too."""
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


def _emit_terminal(line: str) -> None:
    if LINE_SINK is not None:
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
    """FIFO barrier: block until the pump has processed everything written so far; call only once all forked cooks are reaped (nothing writes after the marker)."""
    if LOG_PIPE_WRITE is None:
        return
    marker = uuid.uuid4().hex
    DRAIN_EVENTS[marker] = event = threading.Event()
    os.write(LOG_PIPE_WRITE, f"{marker}\n".encode())
    event.wait(timeout)


def start_logging() -> Path:
    """Open logs/<run>.log and start the pump (redirect fd 1/2 into a pipe one thread reads); honor SHARED_LOG_ENV or create a timestamped file, chowned to SUDO_USER."""
    LOG_DIR.mkdir(exist_ok=True)
    if existing := os.environ.get(SHARED_LOG_ENV):
        log_file = Path(existing)
    else:
        log_file = LOG_DIR / f"sys-conf-py-{datetime.now():%Y%m%d-%H%M%S}.log"
        os.environ[SHARED_LOG_ENV] = str(log_file)
    log_file.touch(exist_ok=True)
    if sudo_user := os.environ.get("SUDO_USER"):
        pw = pwd.getpwnam(sudo_user)
        os.chown(LOG_DIR, pw.pw_uid, pw.pw_gid)
        os.chown(log_file, pw.pw_uid, pw.pw_gid)

    global TERMINAL_FD, LOG_HANDLE, LOG_PIPE_WRITE
    if TERMINAL_FD is None:
        TERMINAL_FD = os.dup(1)
    LOG_HANDLE = open(log_file, "a")

    read_fd, write_fd = os.pipe()
    LOG_PIPE_WRITE = os.dup(write_fd)
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


def log_toon(rows: list[dict], note: str = "") -> None:
    """Log a list of flat dicts as a TOON table, one logger line per row line."""
    if note:
        logger.info(note)
    for line in encode(rows).splitlines():
        logger.info(line)
