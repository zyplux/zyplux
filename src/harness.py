"""Shared cook scaffolding: privilege drop, streamed subprocess wrapping, idempotent file writes, binary discovery, URL fetch (logging lives in logs.py)."""

import os
import pwd
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from urllib.request import Request, urlopen

from loguru import logger

SRC_DIR = Path(__file__).resolve().parent
RECIPE_TOML = SRC_DIR / "recipe.toml"

# sysexits.h EX_TEMPFAIL: cook -> chef.py signal for recoverable failure.
SOFT_FAIL_EXIT = 75


def become_user() -> None:
    """The privilege-drop chokepoint per forked user cook: drop gid, rebuild groups, drop uid, repoint HOME/USER/PATH at SUDO_USER; a no-op under an unprivileged dry-run."""
    if os.geteuid() != 0:
        return
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user:
        sys.exit("ERROR: SUDO_USER not set; chef must be launched via sudo.")
    pw = pwd.getpwnam(sudo_user)
    os.setgid(pw.pw_gid)
    os.initgroups(sudo_user, pw.pw_gid)
    os.setuid(pw.pw_uid)
    home = pw.pw_dir
    os.environ["HOME"] = home
    os.environ["USER"] = sudo_user
    os.environ["LOGNAME"] = sudo_user
    os.environ["XDG_CACHE_HOME"] = f"{home}/.cache"
    # Toolchains install into these before they are on PATH; prepend so a fresh
    # bootstrap can find what an earlier cook just dropped here.
    bootstrap = ":".join(str(d) for d in bootstrap_bin_dirs())
    os.environ["PATH"] = f"{bootstrap}:{os.environ.get('PATH', '')}"


def run(*cmd: str, note: str = "", check: bool = True, **kwargs) -> subprocess.CompletedProcess:
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
    """Run `cmd`, streaming merged stdout/stderr through logger.info; raises CalledProcessError on non-zero unless check=False; TERM=dumb/NO_COLOR/start_new_session suppress ANSI and /dev/tty bypass."""
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
    exit_code = proc.wait()
    if check and exit_code != 0:
        raise subprocess.CalledProcessError(exit_code, cmd)


def write_if_changed(path: Path, content: bytes | str, mode: int = 0o644, note: str = "") -> bool:
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


def bootstrap_bin_dirs() -> tuple[Path, ...]:
    """Dirs rustup/bun/uv install into before they are on PATH, resolved from $HOME at call time so they follow become_user's drop in a forked child."""
    home = Path.home()
    return (
        home / ".cargo/bin",
        home / ".bun/bin",
        home / ".local/bin",
        home / ".claude/local",
    )


def find_binary(name: str) -> Path | None:
    """Look up a binary on PATH, then the bootstrap dirs; user-scope only, since those dirs follow $HOME which become_user repoints in the child."""
    if found := shutil.which(name):
        return Path(found)
    for d in bootstrap_bin_dirs():
        candidate = d / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


USER_AGENT = "sys-conf-py"


def fetch_url(url: str) -> bytes:
    """HTTP GET. Custom UA — Signal/herdr CDNs 403 the urllib default."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        return response.read()
