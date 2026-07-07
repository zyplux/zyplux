"""The single bash-execution chokepoint: every external command a cook runs goes through `run` (capture) or `stream` (live-logged). Import the module and call `shell.run`/`shell.stream` (module-qualified) so a test can mock this one surface."""

import os
import subprocess
import threading
from pathlib import Path

from loguru import logger


def resolve_workdir(cwd: Path | None) -> Path:
    """Where a command runs: $HOME unless overridden. Anchoring to $HOME (not the inherited launch directory) keeps behavior independent of where totchef was invoked — a user `bash` snippet runs as if typed in a terminal, and a vendor installer defaulting to a relative bin dir lands under ~ where find_binary looks. Resolved per call: become_user repoints $HOME inside each forked user cook."""
    return cwd if cwd is not None else Path.home()


def run(
    *cmd: str,
    stdin: bytes | str | None = None,
    text: bool = True,
    check: bool = False,
    timeout: float | None = None,
    note: str = "",
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run a command to completion, capturing stdout+stderr; the one-shot half of the bash boundary (probes that read output). `text=False` keeps bytes for binary stdin/stdout (a GPG de-armor). Runs from $HOME unless `cwd` overrides."""
    if note:
        logger.info(note)
    return subprocess.run(
        list(cmd),
        input=stdin,
        capture_output=True,
        text=text,
        check=check,
        timeout=timeout,
        cwd=resolve_workdir(cwd),
    )


def stream(
    cmd: list[str],
    tag: str = "",
    *,
    note: str = "",
    stdin: bytes | None = None,
    check: bool = True,
    cwd: Path | None = None,
) -> None:
    """Run `cmd`, streaming merged stdout/stderr through logger.info; raises CalledProcessError on non-zero unless check=False; TERM=dumb/NO_COLOR/start_new_session suppress ANSI and /dev/tty bypass. Runs from $HOME unless `cwd` overrides."""
    prefix = f"{tag} " if tag else ""
    if note:
        logger.info(f"{prefix}{note}")
    proc_env = {**os.environ, "TERM": "dumb", "NO_COLOR": "1"}
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=proc_env,
        cwd=resolve_workdir(cwd),
        start_new_session=True,
    )
    proc_stdout = proc.stdout
    assert proc_stdout is not None
    writer: threading.Thread | None = None
    if stdin is not None:
        proc_stdin = proc.stdin
        assert proc_stdin is not None

        def feed_stdin() -> None:
            try:
                proc_stdin.write(stdin)
            finally:
                proc_stdin.close()

        writer = threading.Thread(target=feed_stdin, daemon=True)
        writer.start()
    for raw in proc_stdout:
        decoded = raw.decode("utf-8", errors="replace").rstrip("\n")
        for segment in decoded.split("\r"):
            segment = segment.rstrip()
            if segment:
                logger.info(f"{prefix}{segment}")
    if writer is not None:
        writer.join()
    exit_code = proc.wait()
    if check and exit_code != 0:
        raise subprocess.CalledProcessError(exit_code, cmd)
