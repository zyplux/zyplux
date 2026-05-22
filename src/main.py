#!/usr/bin/env -S uv run
"""Orchestrator for `just up` — runs every playbook as its own subprocess.

Each playbook is spawned via sys.executable (the project venv's python),
so the sudo-requiring ones (configure_with_apt, configure_gpu,
configure_apps) can re-exec themselves under sudo without affecting the
orchestrator — execvp replaces the subprocess, not main.py.

SYS_CONF_PY_LOG_FILE is exported once here so every playbook (including
post-sudo, via --preserve-env in reexec_under_sudo) appends to the same
file. Pre-existing values are honored, so callers can override the log
path: `SYS_CONF_PY_LOG_FILE=/tmp/x.log ./src/main.py`.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from harness import LOG_DIR, SHARED_LOG_ENV

SRC_DIR = Path(__file__).resolve().parent

PLAYBOOKS = [
    "install_from_urls.py",
    "install_cargo_packages.py",
    "install_uv_packages.py",
    "configure_with_apt.py",
    "configure_gpu.py",
    "configure_apps.py",
]


def main() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    os.environ.setdefault(
        SHARED_LOG_ENV,
        str(LOG_DIR / f"sys-conf-py-{datetime.now():%Y%m%d-%H%M%S}.log"),
    )
    subprocess.run(["sudo", "-v"], check=True)
    for playbook in PLAYBOOKS:
        subprocess.run([sys.executable, str(SRC_DIR / playbook)], check=True)


if __name__ == "__main__":
    main()
