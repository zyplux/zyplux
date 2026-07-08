"""Shared cook scaffolding: privilege drop, idempotent writes, find binary, URL fetch (bash: shell.py, log: logs.py)."""

import os
import pwd
import shutil
import stat
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.request import Request, urlopen

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable


class _FilesDir:
    """The pinned totchef_files/ dir for this run, mutated in place so set_files_dir never needs a rebind."""

    path: Path | None = None


_files_dir = _FilesDir()


def set_files_dir(path: Path | None) -> None:
    """Pin the recipe's sibling assets dir (totchef_files/) before any cook reads a bundled `source`; None clears it."""
    _files_dir.path = path


def files_dir() -> Path:
    """The recipe's sibling assets dir; raises if `source` is used before a recipe pinned it (a wiring bug)."""
    if _files_dir.path is None:
        msg = "totchef_files dir not resolved — a bundled `source` was referenced before the recipe was loaded"
        raise RuntimeError(msg)
    return _files_dir.path


def resolve_bundled_source(entry_name: str | None) -> str:
    """The bundled file an omitted `source` defaults to: the totchef_files/ file stemmed by entry name; 0/2+ raises."""
    base = files_dir()
    candidates: list[str] = (
        sorted(path.name for path in base.iterdir() if path.is_file() and path.stem == entry_name)
        if base.is_dir()
        else []
    )
    if len(candidates) == 1:
        return candidates[0]
    problem = (
        f"several bundled files match '{entry_name}': {', '.join(candidates)}"
        if candidates
        else f"no bundled file named '{entry_name}.*' under {base}"
    )
    msg = f"{problem} — set `source` explicitly"
    raise ValueError(msg)


# sysexits.h EX_TEMPFAIL: cook -> chef signal for recoverable failure.
SOFT_FAIL_EXIT = 75


def become_user() -> None:
    """Privilege drop for a forked cook: drop gid, rebuild groups, uid, repoint HOME/USER/PATH; no-op if root-less."""
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
    content_matches = path.exists() and path.read_bytes() == content
    if content_matches and stat.S_IMODE(path.stat().st_mode) == mode:
        logger.info("Unchanged: {path}", path=path)
        return False
    if content_matches:
        logger.info("Chmod    : {path}{note}", path=path, note=f"  ({note})" if note else "")
    else:
        logger.info("Writing  : {path}{note}", path=path, note=f"  ({note})" if note else "")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    path.chmod(mode)
    return True


def bootstrap_bin_dirs() -> tuple[Path, ...]:
    """Dirs rustup/bun/uv install into before PATH, resolved from $HOME, following become_user in a forked child."""
    home = Path.home()
    return (
        home / ".cargo/bin",
        home / ".bun/bin",
        home / ".local/bin",
        home / ".claude/local",
    )


def find_binary(name: str) -> Path | None:
    """Look up a binary on PATH, then bootstrap dirs; user-scope, since those follow become_user's $HOME."""
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
    """Time-bounded HTTP GET (stall raises, never hangs); rejects non-http(s); custom UA — CDNs 403 urllib's default."""
    if not url.startswith(("http://", "https://")):
        msg = f"refusing to fetch {url!r}: only http/https URLs are allowed"
        raise ValueError(msg)
    request = Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310 — scheme validated above; ruff's own preview mode still flags it: https://github.com/astral-sh/ruff/issues/7918
    with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310 — same scheme guard, same acknowledged preview-mode limitation
        return response.read()


def fetch_latest_concurrent(names: list[str], fetch_one: Callable[[str], str | None]) -> dict[str, str | None]:
    """Map each name to its latest via fetch_one, run concurrently; a raising fetch yields None, not a failure."""
    if not names:
        return {}
    latest: dict[str, str | None] = {}
    with ThreadPoolExecutor() as pool:
        pending = {pool.submit(fetch_one, name): name for name in names}
        for future in as_completed(pending):
            name = pending[future]
            try:
                latest[name] = future.result()
            except Exception as exc:  # noqa: BLE001 — fetch_one is a plugin extension point (totchef.cooks); logger.opt(exception=True) is loguru's own idiom for propagating the trace below, but ruff doesn't recognize the .opt() chain as a logging call: https://github.com/astral-sh/ruff/issues/19075
                logger.opt(exception=True).debug("latest lookup for {name} failed: {exc}", name=name, exc=exc)
                latest[name] = None
    return latest
