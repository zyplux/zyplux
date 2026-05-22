"""Shared execution scaffolding for sys-conf-py playbook scripts.

The playbooks share a common shape: re-exec under sudo when needed, tee
stdout/stderr to a per-run log under logs/, and idempotently write system
files. This module owns the plumbing so each playbook can focus on what
it configures. main.py spawns the playbooks as subprocesses under the
project venv's python (uv-managed); harness.py is imported into each.

Exports:
  SRC_DIR              this module's directory (also where the playbook scripts live)
  REPO_ROOT            repo root (parent of src/)
  LOG_DIR              repo_root/logs — where per-run logs land
  BOOTSTRAP_BIN_DIRS   per-user dirs vendor installers write into
  reexec_under_sudo()  re-exec the calling script under sudo if not root
  start_log_tee()      tee stdout+stderr into the shared per-run log
  get_invoking_user()  resolve SUDO_USER → (name, uid, gid, home)
  run()                subprocess.run with optional pre-log of the action
  stream_subprocess()  run subprocess; stream merged stdout/stderr tagged per line
  write_if_changed()   write file only when contents differ (returns bool)
  find_binary()        locate executable via PATH or known bootstrap dirs
  fetch_url()          HTTP GET that survives vendor UA gates (Signal, herdr, …)
"""

import os
import pwd
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from loguru import logger

SRC_DIR = Path(__file__).resolve().parent
REPO_ROOT = SRC_DIR.parent
LOG_DIR = REPO_ROOT / "logs"

LOG_FORMAT = "[{time:YYYY-MM-DD HH:mm:ss}] {extra[runner]: <22} {level: <7} {message}"

SHARED_LOG_ENV = "SYS_CONF_PY_LOG_FILE"

# Configured at import so the pre-sudo "Re-running under sudo" message is also
# timestamped (execvp re-imports this module in the elevated process, which
# re-resolves sys.argv[0] and re-binds the runner name in the elevated logger).
logger.remove()
logger.configure(extra={"runner": Path(sys.argv[0]).stem})
logger.add(sys.stderr, format=LOG_FORMAT, level="INFO", colorize=False)


def reexec_under_sudo(script: Path) -> None:
    if os.geteuid() != 0:
        logger.info("Re-running under sudo")
        os.execvp(
            "sudo",
            [
                "sudo",
                f"--preserve-env={SHARED_LOG_ENV}",
                sys.executable,
                str(script),
                *sys.argv[1:],
            ],
        )


def start_log_tee() -> Path:
    """Tee stdout/stderr into the shared per-run log under logs/.

    If SYS_CONF_PY_LOG_FILE is set (the `just up` umbrella exports it from
    one bash shell so every script it execs inherits it), append to that
    file — the whole run lands in one log. Otherwise (a direct script
    invocation like `./src/configure_gpu.py`), create a fresh
    sys-conf-py-<timestamp>.log and export it so any sudo re-exec inherits
    it via --preserve-env.

    Pre-chowning to SUDO_USER lets root-written content keep the original
    owner — tee runs as root post-sudo but only appends to an already-owned
    file.
    """
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
    tee = subprocess.Popen(["tee", "-a", str(log_file)], stdin=subprocess.PIPE)
    assert tee.stdin is not None
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


def stream_subprocess(
    cmd: list[str],
    tag: str = "",
    *,
    note: str = "",
    stdin: bytes | None = None,
    check: bool = True,
) -> None:
    """Run `cmd` and stream merged stdout/stderr line-by-line through
    logger.info. If `tag` is set, prepend it to each line (and to the
    optional `note` header) so parallel callers stay attributable. If
    `note` is given, log it before the subprocess starts — saves an
    extra logger.info at the call site. Raises CalledProcessError on
    non-zero exit unless `check=False`. A daemon thread feeds `stdin`
    if provided so large inputs don't deadlock against a blocked stdout
    buffer.

    TERM=dumb / NO_COLOR=1 / start_new_session=True together discourage
    ANSI/progress prettification and block /dev/tty bypass (some tools
    open /dev/tty to keep writing to the terminal even when stdout is
    piped; detaching from the controlling tty makes that open fail back
    to the captured pipe). CR-based overwrites inside a chunk are split
    per-frame so each becomes its own prefixed log line instead of
    mashing into one.
    """
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
    rc = proc.wait()
    if check and rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)


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


USER_AGENT = "sys-conf-py"


def fetch_url(url: str) -> bytes:
    """HTTP GET `url`, return the response body as bytes.

    Identifies as `sys-conf-py` rather than the urllib default — vendor CDNs
    behind WAFs (Signal's repo, herdr.dev's installer, likely others) 403 the
    literal `Python-urllib/*` UA but accept any non-default identifier.
    """
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        return response.read()
