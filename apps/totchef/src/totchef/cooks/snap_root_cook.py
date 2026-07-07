"""VersionedCook for [snap] — snap install/refresh via snapd, run sequentially behind snapd's global lock; install failure is hard, refresh soft. Runs as root."""

import shutil
import subprocess

from totchef import shell
from totchef.cook_base import PackageListCook, SyncOutcome


def parse_snap_list(output: str) -> dict[str, str]:
    """Map snap name -> version from `snap list`: skip the header line, take column 0 (name) and column 1 (version) of the rest."""
    versions: dict[str, str] = {}
    for line in output.splitlines():
        if not line or line.startswith("Name"):
            continue
        tokens = line.split()
        versions[tokens[0]] = tokens[1] if len(tokens) > 1 else "unknown"
    return versions


def parse_refresh_list(output: str) -> dict[str, str]:
    """Map snap name -> available version from `snap refresh --list`: same table as `snap list` once past the `Name` header, but skip the 'All snaps up to date.' line (no header) so it isn't read as a row."""
    versions: dict[str, str] = {}
    seen_header = False
    for line in output.splitlines():
        if line.startswith("Name"):
            seen_header = True
            continue
        if not seen_header or not line.strip():
            continue
        tokens = line.split()
        if len(tokens) >= 2:
            versions[tokens[0]] = tokens[1]
    return versions


def parse_installed_snaps() -> dict[str, str]:
    completed = shell.run("snap", "list", check=True)
    return parse_snap_list(completed.stdout)


def find_refreshable_snaps() -> dict[str, str]:
    completed = shell.run("snap", "refresh", "--list")
    return parse_refresh_list(completed.stdout)


class SnapCook(PackageListCook):
    needs_root = True

    def list_installed(self) -> dict[str, str]:
        return parse_installed_snaps() if shutil.which("snap") else {}

    def find_latest(self, names: list[str]) -> dict[str, str | None]:
        if not shutil.which("snap"):
            return dict.fromkeys(names)
        pending = find_refreshable_snaps()
        installed = parse_installed_snaps()
        return {name: pending.get(name) or installed.get(name) for name in names}

    def sync(self, to_install: list[str], to_upgrade: list[str]) -> SyncOutcome:
        work = [("install", n) for n in to_install] + [("refresh", n) for n in to_upgrade]
        if not work:
            return SyncOutcome("ok")
        if shutil.which("snap") is None:
            return SyncOutcome("hard_fail", "snapd is not installed; cannot manage snaps.")

        tag_width = max(len(name) for _, name in work)
        install_failures: list[str] = []
        refresh_failures: list[str] = []
        for verb, name in work:
            try:
                shell.stream(
                    ["snap", verb, name],
                    f"[{name:>{tag_width}}]",
                    note="Installing" if verb == "install" else "Refreshing",
                )
            except subprocess.CalledProcessError:
                (install_failures if verb == "install" else refresh_failures).append(name)

        if install_failures:
            return SyncOutcome("hard_fail", f"snap install failed: {', '.join(install_failures)}")
        if refresh_failures:
            return SyncOutcome(
                "soft_fail",
                f"snap refresh failed (snap stays usable): {', '.join(refresh_failures)}",
            )
        return SyncOutcome("ok")
