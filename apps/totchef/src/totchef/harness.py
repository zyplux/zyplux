"""Shared cook scaffolding: privilege drop, idempotent file writes, binary discovery, URL fetch (bash execution lives in shell.py, logging in logs.py)."""

import os
import pwd
import shutil
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen

from loguru import logger

_files_dir: Path | None = None


def set_files_dir(path: Path | None) -> None:
    """Pin the recipe's sibling assets dir (totchef_files/) for this run, before any cook reads a bundled `source`. None clears it (between tests)."""
    global _files_dir
    _files_dir = path


def files_dir() -> Path:
    """The recipe's sibling assets dir, resolved from the recipe before cooks run; raises if a bundled `source` is referenced before a recipe pinned it (a wiring bug, never a recipe error)."""
    if _files_dir is None:
        raise RuntimeError("totchef_files dir not resolved — a bundled `source` was referenced before the recipe was loaded")
    return _files_dir


def resolve_bundled_source(entry_name: str | None) -> str:
    """The bundled file an omitted `source` defaults to: the unique file under the recipe's totchef_files/ whose stem equals the entry name; zero or several matches raise, asking for an explicit `source`."""
    base = files_dir()
    candidates = sorted(path.name for path in base.iterdir() if path.is_file() and path.stem == entry_name) if base.is_dir() else []
    if len(candidates) == 1:
        return candidates[0]
    problem = f"several bundled files match '{entry_name}': {', '.join(candidates)}" if candidates else f"no bundled file named '{entry_name}.*' under {base}"
    raise ValueError(f"{problem} — set `source` explicitly")


# sysexits.h EX_TEMPFAIL: cook -> chef signal for recoverable failure.
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
    # The user's runtime dir holds the session D-Bus; point at it so `systemctl --user`
    # (e.g. the chezmoi capture timer) can reach the bus instead of failing to connect.
    os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{pw.pw_uid}"
    # Toolchains install into these before they are on PATH; prepend so a fresh
    # bootstrap can find what an earlier cook just dropped here.
    bootstrap = ":".join(str(d) for d in bootstrap_bin_dirs())
    os.environ["PATH"] = f"{bootstrap}:{os.environ.get('PATH', '')}"


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


USER_AGENT = "totchef"
FETCH_TIMEOUT_SECONDS = 30


def assume_https(url: str) -> str:
    """A URL with the scheme omitted means https; an explicit scheme passes through."""
    return url if "://" in url else f"https://{url}"


def fetch_url(url: str) -> bytes:
    """Time-bounded HTTP GET (a stall raises, never hangs). Custom UA — Signal/herdr CDNs 403 the urllib default."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        return response.read()


def fetch_latest_concurrent(names: list[str], fetch_one: Callable[[str], str | None]) -> dict[str, str | None]:
    """Map each name to its upstream latest via fetch_one, run concurrently for a probe pass; a fetch that raises yields None so the caller falls back to 'unknown latest' rather than failing the run."""
    if not names:
        return {}
    latest: dict[str, str | None] = {}
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        pending = {pool.submit(fetch_one, name): name for name in names}
        for future in as_completed(pending):
            name = pending[future]
            try:
                latest[name] = future.result()
            except Exception as exc:
                logger.debug(f"latest lookup for {name} failed: {exc}")
                latest[name] = None
    return latest
