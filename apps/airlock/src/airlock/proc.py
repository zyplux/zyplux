from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class CommandError(RuntimeError):
    def __init__(self, argv: tuple[str, ...], execution: subprocess.CompletedProcess[str]) -> None:
        message = f"command failed with exit code {execution.returncode}: {' '.join(argv)}"
        for stream in (execution.stdout, execution.stderr):
            if stream:
                message += f"\n{stream.strip()}"
        super().__init__(message)


def run(*argv: str, cwd: Path | None = None, stdin: str | None = None, interactive: bool = False) -> str:
    executable = shutil.which(argv[0])
    if executable is None:
        msg = f"`{argv[0]}` not found on PATH"
        raise FileNotFoundError(msg)
    execution = subprocess.run(
        [executable, *argv[1:]],
        cwd=cwd,
        input=stdin,
        stdin=None if interactive or stdin is not None else subprocess.DEVNULL,
        capture_output=not interactive,
        text=True,
        check=False,
    )
    if execution.returncode:
        raise CommandError(argv, execution)
    return (execution.stdout or "").strip()


def find_root(directory: Path | None = None) -> Path:
    return Path(run("git", "rev-parse", "--show-toplevel", cwd=directory))
