"""StateCook for [apt_repo.<name>] — third-party apt repos, each configured with a keyring under /usr/share/keyrings and a `Signed-By:` `.sources` file, both named after the entry. `url` is the repo's base (scheme optional, https assumed): `key_url`/`uris` may be paths relative to it, `uris` defaulting to the base itself; absolute URLs work as before. An optional `pin_priority` writes a `/etc/apt/preferences.d/<name>.pref` pinning the repo's origin to that priority — punch a declared hole through the Ubuntu-archive pin so this repo wins for the packages it ships. Runs as root; depends on bash.apt_prereqs."""

import platform
import sys
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger
from pydantic import model_validator

from totchef import shell
from totchef.cook_base import EntrySpec, StateChangeOutcome, StateCook
from totchef.harness import assume_https, fetch_url, write_if_changed

KEYRINGS_DIR = Path("/usr/share/keyrings")
SOURCES_DIR = Path("/etc/apt/sources.list.d")
PREFERENCES_DIR = Path("/etc/apt/preferences.d")


def resolve_repo_url(base_url: str | None, url: str | None) -> str:
    """Absolute URLs (any scheme) pass through; a relative path — or an omitted `uris` — resolves against the repo's `url`."""
    if url and "://" in url:
        return url
    if base_url is None:
        unresolved = f"relative '{url}'" if url else "an omitted `uris`"
        raise ValueError(f"{unresolved} needs a base to resolve against — set `url` or absolute URLs")
    return f"{base_url}/{url}" if url else base_url


class AptRepoEntry(EntrySpec):
    url: str | None = None
    key_url: str
    uris: str | None = None
    suites: str = "stable"
    components: str = "main"
    architectures: str | None = None
    keyring: str | None = None
    source_path: str | None = None
    pin_priority: int | None = None
    preferences_path: str | None = None

    @model_validator(mode="after")
    def _resolve_urls(self) -> "AptRepoEntry":
        if self.url is not None:
            self.url = assume_https(self.url)
        self.key_url = resolve_repo_url(self.url, self.key_url)
        self.uris = resolve_repo_url(self.url, self.uris)
        return self


def detect_release() -> str:
    os_release = platform.freedesktop_os_release()
    release = os_release.get("VERSION_CODENAME") or os_release.get("UBUNTU_CODENAME")
    if not release:
        sys.exit("ERROR: could not determine release codename")
    return release


def build_keyring_path(name: str, repo: AptRepoEntry) -> Path:
    return Path(repo.keyring) if repo.keyring else KEYRINGS_DIR / f"{name}.gpg"


def build_source_path(name: str, repo: AptRepoEntry) -> Path:
    return Path(repo.source_path) if repo.source_path else SOURCES_DIR / f"{name}.sources"


def build_preferences_path(name: str, repo: AptRepoEntry) -> Path:
    return Path(repo.preferences_path) if repo.preferences_path else PREFERENCES_DIR / f"{name}.pref"


def build_pin_origin(repo: AptRepoEntry) -> str:
    """The site host apt records for this repo — what `Pin: origin <host>` matches — taken from the resolved `uris` (e.g. cli.github.com from https://cli.github.com/packages)."""
    host = urlparse(repo.uris or "").hostname
    if not host:
        raise ValueError(f"cannot derive a pin origin host from uris {repo.uris!r}")
    return host


def render_pin(name: str, origin: str, priority: int) -> str:
    return f"# {name}: prefer this origin's packages (overrides totchef's Ubuntu-archive pin).\nPackage: *\nPin: origin {origin}\nPin-Priority: {priority}\n"


def install_repo_key(name: str, key_url: str, keyring: Path) -> bool:
    data = fetch_url(key_url)
    # ASCII-armored keys start with the RFC 4880 §7.2 header; binary OpenPGP
    # packets start with a high-bit-set tag byte and never match.
    if data.lstrip().startswith(b"-----BEGIN PGP"):
        data = shell.run("gpg", "--dearmor", stdin=data, text=False, check=True).stdout
    return write_if_changed(keyring, data, note=f"{name} GPG key")


def configure_repo(name: str, repo: AptRepoEntry, release: str) -> bool:
    keyring = build_keyring_path(name, repo)
    changed = install_repo_key(name, repo.key_url, keyring)
    lines = [
        "Types: deb",
        f"URIs: {repo.uris}",
        f"Suites: {repo.suites.format(release=release)}",
        f"Components: {repo.components}",
    ]
    # Omitting Architectures: lets apt use the host's dpkg arch (plus any added
    # via `dpkg --add-architecture`); only pin for repos shipping a strict subset.
    if repo.architectures:
        lines.append(f"Architectures: {repo.architectures}")
    lines.append(f"Signed-By: {keyring}")
    changed |= write_if_changed(build_source_path(name, repo), "\n".join(lines) + "\n")
    if repo.pin_priority is not None:
        pin = render_pin(name, build_pin_origin(repo), repo.pin_priority)
        changed |= write_if_changed(build_preferences_path(name, repo), pin)
    return changed


class AptRepoCook(StateCook[AptRepoEntry]):
    needs_root = True
    entry_model = AptRepoEntry

    def get_current_state(self) -> dict[str, str]:
        states: dict[str, str] = {}
        for name, repo in self.entries.items():
            present = build_keyring_path(name, repo).exists() and build_source_path(name, repo).exists()
            if repo.pin_priority is not None:
                present = present and build_preferences_path(name, repo).exists()
            states[name] = "configured" if present else "absent"
        return states

    def get_desired_state(self) -> dict[str, str]:
        return dict.fromkeys(self.entries, "configured")

    def apply_resource(self, name: str) -> StateChangeOutcome:
        release = detect_release()
        logger.info(f"Configuring repo {name} (release codename: {release})")
        changed = configure_repo(name, self.entries[name], release)
        return StateChangeOutcome(changed=changed)
