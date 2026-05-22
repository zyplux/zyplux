#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["loguru>=0.7", "toon-format>=0.9.0b1"]
# ///
"""
Idempotent declarative apt state: repos, keys, pinning, full-upgrade,
package install, autoremove. Idempotent; same script for first-run
bootstrap and ongoing daily-driver maintenance. Actions run through nala
(parallel downloads + `nala history undo` for rollback); nala is
bootstrapped via apt-get on the first run.

Config in apt_config.toml:
  packages       installed at the end of the run
  [ubuntu_pin]   uprank Ubuntu archives ({release} interpolated)
  [[repo]]       one block per third-party apt repo

Repos use the modern layout: GPG key outside /etc/apt/trusted.gpg.d/ +
.sources with `Signed-By:` so each key only authorises its own repo.

Cross-repo safety: apt-preferences upranks Ubuntu main/updates/security
above the default 500, so a third-party package colliding by name with an
Ubuntu one loses to Ubuntu. Third-party-only packages still install at
500. Per-package third-party overrides need a pin > 900 in
/etc/apt/preferences.d/.

Hardening: /etc/apt/trusted.gpg.d/ is chattr +i to block legacy install
scripts that drop keys there. A DPkg::Pre/Post-Invoke hook unlocks it
around dpkg runs so apt and do-release-upgrade still work (prior failure:
release upgrade aborted when ubuntu-keyring couldn't write into it).

Bootstraps from a clean system with just uv (no curl/gnupg required up
front).
"""

import os
import platform
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger
from toon_format import encode

from harness import (
    SRC_DIR,
    fetch_url,
    reexec_under_sudo,
    run,
    start_log_tee,
    write_if_changed,
)

# apt requires files in preferences.d/ to have either no extension or `.pref`.
UBUNTU_PREF = Path("/etc/apt/preferences.d/ubuntu-archives.pref")
TRUSTED_GPGD = Path("/etc/apt/trusted.gpg.d")
TRUSTED_GPGD_HOOK = Path("/etc/apt/apt.conf.d/99-trusted-gpgd-autounlock")

SCRIPT = Path(__file__).resolve()
APT_CONFIG_TOML = SRC_DIR / "apt_config.toml"
FILES_DIR = SRC_DIR / "files"


def nala(*args: str, note: str = "", **kwargs) -> None:
    run("nala", *args, note=note, **kwargs)


def print_toon(rows: list[dict], note: str = "") -> None:
    if note:
        logger.info(note)
    print(encode(rows))


def install_prereqs() -> None:
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"
    run("apt-get", "update", note="Refreshing apt cache")
    run(
        "apt-get",
        "install",
        "-y",
        "--no-install-recommends",
        "curl",
        "gnupg",
        "ca-certificates",
        "nala",
        note="Installing prerequisites",
    )


def build_policy_row(package: str) -> dict:
    """Parse `apt-cache policy <package>` into a flat row for the TOON summary."""
    lines = subprocess.run(
        ["apt-cache", "policy", package], capture_output=True, text=True
    ).stdout.splitlines()

    def field(name: str) -> str:
        prefix = f"{name}:"
        return next(
            (
                line.split(":", 1)[1].strip()
                for line in lines
                if line.strip().startswith(prefix)
            ),
            "(none)",
        )

    candidate = field("Candidate")
    # priority stays int so TOON emits it unquoted; 0 means "no match found".
    priority, source = 0, ""
    inside_candidate_section, inside_version_table = False, False
    for line in lines:
        if line.strip() == "Version table:":
            inside_version_table = True
            continue
        if not inside_version_table:
            continue
        if line.startswith("        "):
            # Skip /var/lib/dpkg/status — apt's "installed on disk" bookkeeping, not a real repo.
            if inside_candidate_section and not source:
                tokens = line.split()
                if len(tokens) >= 2 and tokens[1] != "/var/lib/dpkg/status":
                    source = urlparse(tokens[1]).hostname or tokens[1]
        else:  # version line: " *** VERSION PRIO" or "     VERSION PRIO"
            tokens = line.replace("***", "").split()
            inside_candidate_section = len(tokens) >= 2 and tokens[0] == candidate
            if inside_candidate_section:
                priority = int(tokens[1])
    return {
        "package": package,
        "installed": field("Installed"),
        "candidate": candidate,
        "priority": priority,
        "source": source,
    }


def is_trusted_gpgd_immutable() -> bool:
    completed = subprocess.run(
        ["lsattr", "-d", str(TRUSTED_GPGD)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout:
        return False
    return "i" in completed.stdout.split(maxsplit=1)[0]


def ensure_trusted_gpgd_hardened() -> None:
    write_if_changed(
        TRUSTED_GPGD_HOOK,
        (FILES_DIR / TRUSTED_GPGD_HOOK.name).read_text(),
        note="auto-unlock dir around dpkg runs",
    )
    if is_trusted_gpgd_immutable():
        return
    run(
        "chattr",
        "+i",
        str(TRUSTED_GPGD),
        note=f"Setting immutable bit on {TRUSTED_GPGD}",
    )
    logger.info(
        f"{TRUSTED_GPGD} is now immutable. Apt/dpkg operations unlock it automatically "
        f"via {TRUSTED_GPGD_HOOK}, so distro upgrades work. "
        f"To make a manual change there: sudo chattr -i {TRUSTED_GPGD}"
    )


def detect_release() -> str:
    osr = platform.freedesktop_os_release()
    release = osr.get("VERSION_CODENAME") or osr.get("UBUNTU_CODENAME")
    if not release:
        sys.exit("ERROR: could not determine release codename")
    return release


def write_ubuntu_pin(pin: dict, release: str) -> None:
    blocks = "\n\n".join(
        f"Package: *\nPin: release o=Ubuntu, a={s.format(release=release)}\nPin-Priority: {pin['priority']}"
        for s in pin["suites"]
    )
    tmpl = (FILES_DIR / UBUNTU_PREF.name).read_text()
    write_if_changed(
        UBUNTU_PREF,
        tmpl.format(priority=pin["priority"], pin_blocks=blocks),
        note="uprank Ubuntu archives above third-party default",
    )


def apply_debconf_selections(selections: list[dict]) -> None:
    if not selections:
        return
    logger.info(
        f"Applying {len(selections)} debconf selection(s): "
        + ", ".join(s["package"] for s in selections)
    )
    payload = "\n".join(
        f"{s['package']} {s['question']} {s['type']} {s['value']}"
        for s in selections
    )
    run("debconf-set-selections", input=payload.encode())


def install_repo_key(repo: dict, keyring: Path) -> None:
    logger.info(f"Installing {repo['name']} GPG key to {keyring}")
    keyring.parent.mkdir(parents=True, exist_ok=True)
    data = fetch_url(repo["key_url"])
    # ASCII-armored keys start with the RFC 4880 §6.2 header; binary OpenPGP
    # packets start with a high-bit-set tag byte and never match.
    if data.lstrip().startswith(b"-----BEGIN PGP"):
        run("gpg", "--dearmor", "--yes", "-o", str(keyring), input=data)
    else:
        keyring.write_bytes(data)
    keyring.chmod(0o644)


def configure_repo(repo: dict, release: str) -> None:
    name = repo["name"]
    keyring = Path(repo.get("keyring", f"/usr/share/keyrings/{name}.gpg"))
    source = Path(repo.get("source_path", f"/etc/apt/sources.list.d/{name}.sources"))
    install_repo_key(repo, keyring)
    lines = [
        "Types: deb",
        f"URIs: {repo['uris']}",
        f"Suites: {repo.get('suites', 'stable').format(release=release)}",
        f"Components: {repo.get('components', 'main')}",
    ]
    # Omitting Architectures: lets apt use the host's dpkg arch (plus any
    # added via `dpkg --add-architecture`); only pin for repos that ship a
    # strict subset of arches the host supports.
    if archs := repo.get("architectures"):
        lines.append(f"Architectures: {archs}")
    lines.append(f"Signed-By: {keyring}")
    write_if_changed(source, "\n".join(lines) + "\n")


def main() -> None:
    # Load config pre-sudo so TOML errors surface before the sudo re-exec.
    with APT_CONFIG_TOML.open("rb") as f:
        config = tomllib.load(f)
    repos = config.get("repo", [])
    packages = config.get("packages", [])

    reexec_under_sudo(SCRIPT)

    log_file = start_log_tee(SCRIPT)
    logger.info(f"Logging this run to {log_file}")
    logger.info(
        f"Loaded config from {APT_CONFIG_TOML} ({len(repos)} repo(s), {len(packages)} package(s))"
    )

    release = detect_release()
    logger.info(f"Detected release codename: {release}")

    ensure_trusted_gpgd_hardened()
    write_ubuntu_pin(config["ubuntu_pin"], release)
    apply_debconf_selections(config.get("debconf", []))

    install_prereqs()

    for repo in repos:
        configure_repo(repo, release)

    nala("update", note="Refreshing apt cache with new repos")
    # `nala list --upgradable` exits 1 when nothing matches (grep convention).
    nala("list", "--upgradable", note="Upgradable packages:", check=False)

    rows = [build_policy_row(p) for p in packages]
    print_toon(
        rows,
        note="Verification — installed/candidate versions and effective pin priorities:",
    )
    # Fail fast before full-upgrade: priority 0 = package not found in any configured repo.
    # Cheaper than letting nala discover it half a minute into the install transaction.
    if missing := [r["package"] for r in rows if r["priority"] == 0]:
        sys.exit(
            f"ERROR: package(s) not available in any configured repo: {', '.join(missing)}\n"
            "  - Check release-specific naming (e.g. libva-nvidia-driver -> nvidia-vaapi-driver on Ubuntu 26.04+).\n"
            "  - Confirm the package's component is enabled (main / universe / multiverse / restricted).\n"
            "  - For a third-party package, confirm its [[repo]] block is in apt_config.toml."
        )

    nala("full-upgrade", "-y", note="Running nala full-upgrade")

    run(
        "lsattr",
        "-d",
        str(TRUSTED_GPGD),
        note=f"{TRUSTED_GPGD} attributes (expect 'i' set):",
    )

    if packages:
        nala(
            "install",
            "-y",
            *packages,
            note=f"Installing packages: {' '.join(packages)}",
        )

    nala("autoremove", "-y", note="Removing unused packages with nala autoremove")

    logger.info(
        f"Done. Configured {len(repos)} repo(s) and {len(packages)} package(s)."
    )


if __name__ == "__main__":
    main()
