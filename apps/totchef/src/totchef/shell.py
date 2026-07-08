(
    """The single bash-execution chokepoint: every command goes through `run` (capture) or `stream` """
    """(live-logged); call module-qualified so tests can mock it."""
)

import os
import subprocess
import threading
from pathlib import Path
from typing import Literal, TypedDict, Unpack, overload

from loguru import logger


def _require_pipe[T](pipe: T | None, what: str) -> T:
    (
        """Narrow a Popen pipe attribute the call itself guaranteed (stdin=/stdout=PIPE); its absence is a """
        """wiring bug, never a runtime condition."""
    )
    if pipe is None:
        msg = f"Popen did not provide a {what} stream despite requesting PIPE"
        raise RuntimeError(msg)
    return pipe


def resolve_workdir(cwd: Path | None) -> Path:
    (
        """Where a command runs: $HOME unless overridden, independent of totchef's invocation dir. """
        """become_user repoints $HOME per forked cook."""
    )
    return cwd if cwd is not None else Path.home()


class RunOptions(TypedDict, total=False):
    (
        """Knobs `run` takes beyond the command and `text` (plain, so Literal overloads discriminate the """
        """return type); bundled to stay under the arg limit."""
    )

    stdin: bytes | str | None
    check: bool
    timeout: float | None
    note: str
    cwd: Path | None


@overload
def run(*cmd: str, text: Literal[True] = True, **options: Unpack[RunOptions]) -> subprocess.CompletedProcess[str]: ...
@overload
def run(*cmd: str, text: Literal[False], **options: Unpack[RunOptions]) -> subprocess.CompletedProcess[bytes]: ...
def run(
    *cmd: str, text: bool = True, **options: Unpack[RunOptions]
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    (
        """Run a command to completion, capturing stdout+stderr; the one-shot half of the bash boundary. """
        """`text=False` keeps bytes (a GPG de-armor)."""
    )
    note = options.get("note", "")
    if note:
        logger.info(note)
    return subprocess.run(
        list(cmd),
        input=options.get("stdin"),
        capture_output=True,
        text=text,
        check=options.get("check", False),
        timeout=options.get("timeout"),
        cwd=resolve_workdir(options.get("cwd")),
    )


class StreamOptions(TypedDict, total=False):
    (
        """The independent knobs `stream` takes beyond `cmd`/`tag`; bundled here so the function signature """
        """itself stays within the positional-argument limit."""
    )

    note: str
    stdin: bytes | None
    check: bool
    cwd: Path | None


def stream(cmd: list[str], tag: str = "", **options: Unpack[StreamOptions]) -> None:
    (
        """Run `cmd`, streaming merged stdout/stderr through logger.info; raises CalledProcessError on """
        """non-zero unless check=False. $HOME unless `cwd` overrides."""
    )
    prefix = f"{tag} " if tag else ""
    note = options.get("note", "")
    if note:
        logger.info("{prefix}{note}", prefix=prefix, note=note)
    stdin = options.get("stdin")
    proc_env = {**os.environ, "TERM": "dumb", "NO_COLOR": "1"}
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=proc_env,
        cwd=resolve_workdir(options.get("cwd")),
        start_new_session=True,
    )
    proc_stdout = _require_pipe(proc.stdout, "stdout")
    writer: threading.Thread | None = None
    if stdin is not None:
        proc_stdin = _require_pipe(proc.stdin, "stdin")

        def feed_stdin() -> None:
            try:
                proc_stdin.write(stdin)
            finally:
                proc_stdin.close()

        writer = threading.Thread(target=feed_stdin, daemon=True)
        writer.start()
    for raw in proc_stdout:
        decoded = raw.decode("utf-8", errors="replace").rstrip("\n")
        for raw_segment in decoded.split("\r"):
            segment = raw_segment.rstrip()
            if segment:
                logger.info("{prefix}{segment}", prefix=prefix, segment=segment)
    if writer is not None:
        writer.join()
    exit_code = proc.wait()
    if options.get("check", True) and exit_code != 0:
        raise subprocess.CalledProcessError(exit_code, cmd)
