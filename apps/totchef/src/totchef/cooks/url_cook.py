(
    """Cook for [url.<name>] — vendor `curl | bash` bootstrappers as a presence-only VersionedCook """
    """(install-if-missing / upgrade-if-present); a `url` without a scheme means https. Install errors hard, """
    """update errors soft. Runs as the invoking user."""
)

import re
import shlex
import subprocess
from typing import TYPE_CHECKING, Literal, override

from loguru import logger
from pydantic import Field, model_validator

from totchef import shell
from totchef.cook_base import EntrySpec, SyncOutcome, VersionedCook
from totchef.harness import assume_https, fetch_url, find_binary

if TYPE_CHECKING:
    from pathlib import Path

    from totchef.recipe_types import RecipeConfig

RERUN_INSTALLER = "rerun-installer"
EMPTY_UPDATE_ACTION_ERROR = (
    f"update_action must be a non-empty arg list, {RERUN_INSTALLER!r}, or absent — an empty list is none of these"
)

VERSION_PATTERN = re.compile(r"\d+\.\d+(?:\.\d+)*")


def parse_version(output: str) -> str:
    (
        """Pull the first dotted version out of a `--version` line; vendors format it freely """
        """('rustup 1.29.0 (…)', '1.3.14', '2.1.150 (Claude Code)'), so fall back to 'present' when nothing """
        """matches."""
    )
    first_line = next((line for line in output.splitlines() if line.strip()), "")
    match = VERSION_PATTERN.search(first_line)
    return match.group() if match else "present"


def probe_version(bin_path: Path) -> str:
    (
        """Best-effort installed version of a vendor CLI; presence is what the cook actually diffs, so any """
        """probe failure degrades to 'present' rather than raising."""
    )
    try:
        completed = shell.run(str(bin_path), "--version", timeout=5)
    except OSError, subprocess.SubprocessError:
        return "present"
    return parse_version(completed.stdout or completed.stderr)


class UrlEntry(EntrySpec):
    url: str
    bin: str | None = None
    args: list[str] = Field(default_factory=list)
    update_action: list[str] | Literal["rerun-installer"] | None = None
    update_guard: str | None = None

    @model_validator(mode="after")
    def _assume_https(self) -> UrlEntry:
        self.url = assume_https(self.url)
        return self

    @model_validator(mode="after")
    def _reject_empty_update_action(self) -> UrlEntry:
        if isinstance(self.update_action, list) and not self.update_action:
            raise ValueError(EMPTY_UPDATE_ACTION_ERROR)
        return self


def run_installer(url: str, args: list[str], note: str) -> None:
    shell.stream(["bash", "-s", "--", *args], note=note, stdin=fetch_url(url))


def update_existing(entry: UrlEntry, bin_path: Path) -> None:
    (
        """Run `entry.update_action` against an already-installed binary; `entry_model` already rejects an """
        """empty arg list, so every remaining shape here is a real action."""
    )
    action = entry.update_action
    if action is None:
        logger.info("No update_action; leaving {bin_path} as-is", bin_path=bin_path)
        return
    if guard := entry.update_guard:
        guard_command = f"PATH={shlex.quote(str(bin_path.parent))}:$PATH; {guard}"
        shell.stream(["bash", "-c", guard_command], note=f"Update guard: {guard}")
    if action == RERUN_INSTALLER:
        run_installer(entry.url, entry.args, note=f"Updating from {entry.url}")
    elif isinstance(action, list):
        shell.stream(
            [str(bin_path), *action],
            note=f"Updating via `{bin_path.name} {' '.join(action)}`",
        )


class UrlCook(VersionedCook):
    entry_model = UrlEntry
    entry_keyed = True

    def __init__(self, section: RecipeConfig) -> None:
        super().__init__(section)
        self.installs = {name: UrlEntry.model_validate(raw) for name, raw in section.items()}

    @override
    def list_requested(self) -> list[str]:
        return list(self.installs)

    @override
    def get_hooks(self) -> tuple[str | None, str | None]:
        [entry] = self.installs.values()
        return (entry.pre_hook, entry.post_hook)

    @override
    def list_installed(self) -> dict[str, str]:
        found = {name: find_binary(entry.bin or name) for name, entry in self.installs.items()}
        return {name: probe_version(path) for name, path in found.items() if path}

    @override
    def find_latest(self, names: list[str]) -> dict[str, str | None]:
        return dict.fromkeys(names)

    @override
    def sync(self, to_install: list[str], to_upgrade: list[str]) -> SyncOutcome:
        if not (to_install or to_upgrade):
            return SyncOutcome("ok")

        [(name, entry)] = self.installs.items()
        bin_name = entry.bin or name

        if (existing := find_binary(bin_name)) is None:
            try:
                run_installer(entry.url, entry.args, note=f"Installing {entry.url}")
            except (OSError, subprocess.CalledProcessError, ValueError) as exc:
                return SyncOutcome("hard_fail", f"{name} install failed: {exc}")
            if found := find_binary(bin_name):
                logger.info("Installed: {found}", found=found)
            else:
                logger.warning("{bin_name} not found after install", bin_name=bin_name)
            return SyncOutcome("ok")

        try:
            update_existing(entry, existing)
        except (subprocess.CalledProcessError, ValueError) as exc:
            return SyncOutcome("soft_fail", f"{name} update failed (still installed): {exc}")
        return SyncOutcome("ok")
