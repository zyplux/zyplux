"""Cook for [url.<name>] — vendor `curl | bash` bootstrappers as a presence-only VersionedCook (install-if-missing / upgrade-if-present); install errors hard, update errors soft. Runs as the invoking user."""

import shlex
import subprocess
from pathlib import Path
from typing import Literal

from loguru import logger

from cook_base import EntrySpec, SyncOutcome, VersionedCook
from harness import fetch_url, find_binary, stream_subprocess

RERUN_INSTALLER = "rerun-installer"


class UrlEntry(EntrySpec):
    url: str
    bin: str | None = None
    args: list[str] = []
    update_action: list[str] | Literal["rerun-installer"] | None = None
    update_guard: str | None = None


def run_installer(url: str, args: list[str], note: str) -> None:
    stream_subprocess(["bash", "-s", "--", *args], note=note, stdin=fetch_url(url))


def update_existing(entry: UrlEntry, bin_path: Path) -> None:
    action = entry.update_action
    if action is None:
        logger.info(f"No update_action; leaving {bin_path} as-is")
        return
    if guard := entry.update_guard:
        shell = f"PATH={shlex.quote(str(bin_path.parent))}:$PATH; {guard}"
        stream_subprocess(["bash", "-c", shell], note=f"Update guard: {guard}")
    if action == RERUN_INSTALLER:
        run_installer(entry.url, entry.args, note=f"Updating from {entry.url}")
    elif isinstance(action, list) and action:
        stream_subprocess(
            [str(bin_path), *action],
            note=f"Updating via `{bin_path.name} {' '.join(action)}`",
        )
    else:
        raise ValueError(f"unrecognized update_action {action!r} (expected an arg list, {RERUN_INSTALLER!r}, or absent)")


class UrlCook(VersionedCook):
    manager = "curl|bash"
    entry_model = UrlEntry

    def __init__(self, section: dict) -> None:
        super().__init__(section)
        self.installs = {name: UrlEntry.model_validate(raw) for name, raw in section.items()}

    def list_requested(self) -> list[str]:
        return list(self.installs)

    def list_installed(self) -> dict[str, str]:
        return {name: "present" for name, entry in self.installs.items() if find_binary(entry.bin or name)}

    def find_latest(self, names: list[str]) -> dict[str, str | None]:
        return dict.fromkeys(names)

    def sync(self, to_install: list[str], to_upgrade: list[str]) -> SyncOutcome:
        if not (to_install or to_upgrade):
            return SyncOutcome("ok")

        [(name, entry)] = self.installs.items()
        bin_name = entry.bin or name

        if (existing := find_binary(bin_name)) is None:
            try:
                run_installer(entry.url, entry.args, note=f"Installing {entry.url}")
            except Exception as exc:
                return SyncOutcome("hard_fail", f"{name} install failed: {exc}")
            if found := find_binary(bin_name):
                logger.info(f"Installed: {found}")
            else:
                logger.warning(f"{bin_name} not found after install")
            return SyncOutcome("ok")

        try:
            update_existing(entry, existing)
        except subprocess.CalledProcessError as exc:
            return SyncOutcome("soft_fail", f"{name} update failed (still installed): {exc}")
        return SyncOutcome("ok")
