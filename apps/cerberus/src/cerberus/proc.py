from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class ToolNotFoundError(RuntimeError):
    def __init__(self, tool: str) -> None:
        super().__init__(f"`{tool}` not found on PATH")


def run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """The single audited subprocess boundary for cerberus.

    `argv[0]` is resolved to an absolute path via PATH, `argv[1:]` are
    program-constructed (never user-derived), and the shell is never invoked, so
    there is no command-injection surface. This is the one place that touches
    `subprocess`.
    """
    executable = shutil.which(argv[0])
    if executable is None:
        raise ToolNotFoundError(argv[0])
    return subprocess.run([executable, *argv[1:]], capture_output=True, text=True, check=False, cwd=cwd)
