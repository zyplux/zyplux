"""VersionedCook for [snap] — snap install/refresh via snapd, run sequentially behind snapd's global lock; install failure is hard, refresh soft. Runs as root."""

import shutil
import subprocess

from cook_base import PackageListCook, SyncOutcome
from harness import stream_subprocess


def parse_snap_list(output: str) -> dict[str, str]:
    """Map snap name -> version from `snap list`: skip the header line, take column 0 (name) and column 1 (version) of the rest."""
    versions: dict[str, str] = {}
    for line in output.splitlines():
        if not line or line.startswith("Name"):
            continue
        tokens = line.split()
        versions[tokens[0]] = tokens[1] if len(tokens) > 1 else "unknown"
    return versions


def parse_installed_snaps() -> dict[str, str]:
    completed = subprocess.run(["snap", "list"], capture_output=True, text=True, check=True)
    return parse_snap_list(completed.stdout)


class SnapCook(PackageListCook):
    needs_root = True
    manager = "snap"

    def list_installed(self) -> dict[str, str]:
        return parse_installed_snaps() if shutil.which("snap") else {}

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
                stream_subprocess(
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
