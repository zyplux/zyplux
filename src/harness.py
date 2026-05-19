"""Shared execution scaffolding for sys-conf-py playbook scripts.

These scripts are PEP 723 single-file installers that share a common shape:
re-exec under sudo, tee stdout/stderr to a timestamped log under logs/, and
idempotently write system files. This module owns the plumbing so each
playbook script can focus on what it configures.

Exports:
  SRC_DIR              this module's directory (also where the playbook scripts live)
  REPO_ROOT            repo root (parent of src/)
  LOG_DIR              repo_root/logs — where per-run logs land
  BOOTSTRAP_BIN_DIRS   per-user dirs vendor installers write into
  reexec_under_sudo()  re-exec the calling script under sudo if not root
  start_log_tee()      mirror stdout+stderr into a timestamped logfile
  get_invoking_user()  resolve SUDO_USER → (name, uid, gid, home)
  run()                subprocess.run with optional pre-log of the action
  write_if_changed()   write file only when contents differ (returns bool)
  find_binary()        locate executable via PATH or known bootstrap dirs
"""

import os
import pwd
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

SRC_DIR = Path(__file__).resolve().parent
REPO_ROOT = SRC_DIR.parent
LOG_DIR = REPO_ROOT / "logs"

LOG_FORMAT = "[{time:YYYY-MM-DD HH:mm:ss}] {level: <7} {message}"

# Configured at import so the pre-sudo "Re-running under sudo" message is also
# timestamped (execvp re-imports this module in the elevated process).
logger.remove()
logger.add(sys.stderr, format=LOG_FORMAT, level="INFO", colorize=False)


def reexec_under_sudo(script: Path) -> None:
    if os.geteuid() != 0:
        logger.info("Re-running under sudo")
        os.execvp("sudo", ["sudo", sys.executable, str(script), *sys.argv[1:]])


def start_log_tee(script: Path) -> Path:
    """Mirror stdout/stderr into logs/<stem>-<timestamp>.log.

    Pre-chowning to SUDO_USER lets root-written content keep the original
    owner — tee runs as root post-sudo but only appends to an already-owned
    file.
    """
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"{script.stem}-{datetime.now():%Y%m%d-%H%M%S}.log"
    log_file.touch()
    if sudo_user := os.environ.get("SUDO_USER"):
        pw = pwd.getpwnam(sudo_user)
        for p in (LOG_DIR, *LOG_DIR.iterdir()):
            os.chown(p, pw.pw_uid, pw.pw_gid)
    tee = subprocess.Popen(["tee", "-a", str(log_file)], stdin=subprocess.PIPE)
    os.dup2(tee.stdin.fileno(), 1)
    os.dup2(tee.stdin.fileno(), 2)
    tee.stdin.close()
    return log_file


def get_invoking_user() -> tuple[str, int, int, Path]:
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user:
        sys.exit("ERROR: SUDO_USER not set; run via sudo, not as root directly.")
    pw = pwd.getpwnam(sudo_user)
    return sudo_user, pw.pw_uid, pw.pw_gid, Path(pw.pw_dir)


def run(
    *cmd: str, note: str = "", check: bool = True, **kwargs
) -> subprocess.CompletedProcess:
    if note:
        logger.info(note)
    return subprocess.run(list(cmd), check=check, **kwargs)


def write_if_changed(
    path: Path, content: bytes | str, mode: int = 0o644, note: str = ""
) -> bool:
    if isinstance(content, str):
        content = content.encode()
    if path.exists() and path.read_bytes() == content:
        logger.info(f"Unchanged: {path}")
        return False
    logger.info(f"Writing  : {path}" + (f"  ({note})" if note else ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    path.chmod(mode)
    return True


BOOTSTRAP_BIN_DIRS = (
    Path.home() / ".cargo/bin",
    Path.home() / ".bun/bin",
    Path.home() / ".local/bin",
    Path.home() / ".claude/local",
)


def find_binary(name: str) -> Path | None:
    """Resolve `name` to an absolute path via PATH first, then known per-user
    bootstrap dirs (vendor installers like rustup, bun, uv land here without
    necessarily being on PATH yet). Returns None if not found.

    Path.home() is read at module import — only call from scripts that run as
    the invoking user, not after a sudo re-exec (where HOME flips to /root).
    """
    if found := shutil.which(name):
        return Path(found)
    for d in BOOTSTRAP_BIN_DIRS:
        candidate = d / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None
