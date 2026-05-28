"""VersionedCook for [apt_pkg] — package install/upgrade via nala, using `apt-cache policy` for a cheap candidate version and always running nala's full system transaction. Runs as root; depends on [bash] and [apt_repo]."""

import os
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from totchef import shell
from totchef.cook_base import PackageListCook, SyncOutcome
from totchef.logs import log_toon

TRUSTED_GPGD = Path("/etc/apt/trusted.gpg.d")


def nala(*args: str, note: str = "", check: bool = True) -> None:
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"
    shell.stream(["nala", *args], note=note, check=check)


def parse_policy(package: str, output: str) -> dict:
    """Parse `apt-cache policy <package>` output into a flat row for the TOON summary."""
    lines = output.splitlines()

    def field(name: str) -> str:
        prefix = f"{name}:"
        return next(
            (line.split(":", 1)[1].strip() for line in lines if line.strip().startswith(prefix)),
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


def build_policy_row(package: str) -> dict:
    output = shell.run("apt-cache", "policy", package).stdout
    return parse_policy(package, output)


class AptPkgCook(PackageListCook):
    needs_root = True

    def __init__(self, section: dict) -> None:
        super().__init__(section)
        self._policy_cache: dict[str, dict] = {}

    def _get_policy(self, package: str) -> dict:
        # Cache within one probe pass so list_installed + find_latest share
        # a single apt-cache call per package.
        if package not in self._policy_cache:
            self._policy_cache[package] = build_policy_row(package)
        return self._policy_cache[package]

    def _refresh_policy(self, package: str) -> dict:
        self._policy_cache.pop(package, None)
        return self._get_policy(package)

    def list_installed(self) -> dict[str, str]:
        # Bust the cache so a probe after sync sees post-transaction versions.
        self._policy_cache.clear()
        return {p: row["installed"] for p in self.packages if (row := self._get_policy(p))["installed"] != "(none)"}

    def find_latest(self, names: list[str]) -> dict[str, str | None]:
        return {p: (None if (c := self._get_policy(p)["candidate"]) == "(none)" else c) for p in names}

    def sync(self, to_install: list[str], to_upgrade: list[str]) -> SyncOutcome:
        nala("update", note="Refreshing apt cache")
        # `nala list --upgradable` exits 1 when nothing matches (grep convention).
        nala("list", "--upgradable", note="Upgradable packages:", check=False)

        rows = [self._refresh_policy(p) for p in self.packages]
        log_toon(
            rows,
            note="Verification — installed/candidate versions and effective pin priorities:",
        )
        # Fail fast before full-upgrade: priority 0 = not found in any configured repo.
        if missing := [r["package"] for r in rows if r["priority"] == 0]:
            return SyncOutcome(
                "hard_fail",
                f"package(s) not available in any configured repo: {', '.join(missing)}\n"
                "  - Check release-specific naming (e.g. libva-nvidia-driver -> nvidia-vaapi-driver on Ubuntu 26.04+).\n"
                "  - Confirm the package's component is enabled (main / universe / multiverse / restricted).\n"
                "  - For a third-party package, confirm its [apt_repo.<name>] subtable is in recipe.toml.",
            )

        nala("full-upgrade", "-y", note="Running nala full-upgrade")
        shell.stream(
            ["lsattr", "-d", str(TRUSTED_GPGD)],
            note=f"{TRUSTED_GPGD} attributes (expect 'i' set):",
        )
        if self.packages:
            nala(
                "install",
                "-y",
                *self.packages,
                note=f"Installing packages: {' '.join(self.packages)}",
            )
        nala("autoremove", "-y", note="Removing unused packages with nala autoremove")
        logger.info(f"Done. Installed/upgraded {len(self.packages)} package(s).")
        return SyncOutcome("ok")
