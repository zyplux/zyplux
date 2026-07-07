"""StateCook for [chezmoi] — provision a dotfiles repo for one-way capture: clone it into source_dir, persist chezmoi's config (sourceDir plus a pinned umask for deterministic file modes), and install a systemd user service+timer that runs `chezmoi re-add` every timer_min minutes to capture $HOME edits back into the repo and auto-commit/push them. The sync is one-way ($HOME → repo); seeding a fresh machine the other way is a manual `chezmoi apply`. Idempotent and user-scoped, gated on [url.chezmoi] for the binary."""

import os
import subprocess
from pathlib import Path

from pydantic import Field

from totchef import harness, shell
from totchef.cook_base import CookBase, EntrySpec, StateChangeOutcome, StateCook

RESOURCE = "dotfiles"
# chezmoi's own default source directory; overridable per recipe.
DEFAULT_SOURCE_DIR = "~/.local/share/chezmoi"
CAPTURE_SERVICE = "chezmoi-capture.service"
CAPTURE_TIMER = "chezmoi-capture.timer"
# chezmoi derives a regular file's target mode from `0o666 &^ umask` (it ignores the
# source file's own mode), so pinning the umask in chezmoi's config keeps a later manual
# `chezmoi apply` deterministic whether it runs from a login shell (umask 002) or totchef's
# sudo context (umask 022); without it the same source applies different modes each way.
CONFIG_UMASK = "0o022"

SERVICE_UNIT = (
    "[Unit]\nDescription=Capture $HOME edits into the chezmoi dotfiles source repo\n\n[Service]\nType=oneshot\nExecStart=%h/.local/bin/chezmoi re-add\n"
).encode()


class ChezmoiEntry(EntrySpec):
    repo: str
    source_dir: str = DEFAULT_SOURCE_DIR
    auto_commit: bool = True
    auto_push: bool = True
    timer_min: int = Field(default=15, gt=0)


class ChezmoiCook(StateCook[ChezmoiEntry]):
    """The single flat [chezmoi] section is one resource, so it validates the slice directly into one synthetic `dotfiles` entry rather than the subtable map StateCook assumes."""

    entry_model = ChezmoiEntry
    entry_keyed = False

    def __init__(self, section: dict) -> None:
        CookBase.__init__(self, section)
        self.entries = {RESOURCE: ChezmoiEntry.model_validate(section)}

    @property
    def spec(self) -> ChezmoiEntry:
        return self.entries[RESOURCE]

    def _source_path(self) -> Path:
        return Path(self.spec.source_dir).expanduser()

    def _config_home(self) -> Path:
        """$XDG_CONFIG_HOME (else ~/.config); resolved per call so a forked user cook's repointed $HOME is honored."""
        return Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config"))

    def _config_path(self) -> Path:
        """chezmoi reads its config from $XDG_CONFIG_HOME/chezmoi (else ~/.config/chezmoi); write it there so the operator's bare chezmoi commands find the same source."""
        return self._config_home() / "chezmoi" / "chezmoi.toml"

    def _user_unit_dir(self) -> Path:
        """Where systemd looks for the operator's user units ($XDG_CONFIG_HOME/systemd/user, else ~/.config/systemd/user)."""
        return self._config_home() / "systemd" / "user"

    def _config_bytes(self) -> bytes:
        """chezmoi's config: the sourceDir, a pinned umask (deterministic apply modes), and a [git] block when auto-commit/push are on so `chezmoi re-add` self-commits and pushes captured $HOME edits."""
        lines = [f'sourceDir = "{self.spec.source_dir}"', f"umask = {CONFIG_UMASK}"]
        git = []
        if self.spec.auto_commit:
            git.append("autoCommit = true")
        if self.spec.auto_push:
            git.append("autoPush = true")
        if git:
            lines += ["", "[git]", *git]
        return ("\n".join(lines) + "\n").encode()

    def _timer_bytes(self) -> bytes:
        """A user timer firing `chezmoi re-add` every timer_min minutes (and shortly after boot, catching up missed runs)."""
        return (
            "[Unit]\nDescription=Periodically capture $HOME into the chezmoi dotfiles repo\n\n"
            f"[Timer]\nOnBootSec=1min\nOnUnitActiveSec={self.spec.timer_min}min\nPersistent=true\n\n"
            "[Install]\nWantedBy=timers.target\n"
        ).encode()

    def _is_cloned(self) -> bool:
        return (self._source_path() / ".git").is_dir()

    def _config_current(self) -> bool:
        path = self._config_path()
        return path.exists() and path.read_bytes() == self._config_bytes()

    def _units_installed(self) -> bool:
        unit_dir = self._user_unit_dir()
        wanted = {CAPTURE_SERVICE: SERVICE_UNIT, CAPTURE_TIMER: self._timer_bytes()}
        return all((unit_dir / unit).exists() and (unit_dir / unit).read_bytes() == content for unit, content in wanted.items())

    def _timer_enabled(self) -> bool:
        return (self._user_unit_dir() / "timers.target.wants" / CAPTURE_TIMER).is_symlink()

    def get_desired_state(self) -> dict[str, str]:
        return {RESOURCE: "capturing"}

    def get_current_state(self) -> dict[str, str]:
        if harness.find_binary("chezmoi") is None:
            return {RESOURCE: "chezmoi-missing"}
        if not self._is_cloned():
            return {RESOURCE: "uncloned"}
        if not self._config_current():
            return {RESOURCE: "unconfigured"}
        if not (self._units_installed() and self._timer_enabled()):
            return {RESOURCE: "capture-pending"}
        return self.get_desired_state()

    def _setup_capture(self) -> None:
        """Install the capture service+timer units, then enable the timer without a session D-Bus (write the timers.target.wants symlink `systemctl --user enable` would create) and best-effort start it — so a later `chezmoi re-add` runs on schedule."""
        unit_dir = self._user_unit_dir()
        harness.write_if_changed(unit_dir / CAPTURE_SERVICE, SERVICE_UNIT, note=CAPTURE_SERVICE)
        harness.write_if_changed(unit_dir / CAPTURE_TIMER, self._timer_bytes(), note=CAPTURE_TIMER)
        wants = unit_dir / "timers.target.wants"
        wants.mkdir(parents=True, exist_ok=True)
        link = wants / CAPTURE_TIMER
        link.unlink(missing_ok=True)
        link.symlink_to(Path("..") / CAPTURE_TIMER)
        shell.run("systemctl", "--user", "daemon-reload")
        shell.run("systemctl", "--user", "start", CAPTURE_TIMER)

    def apply_resource(self, name: str) -> StateChangeOutcome:
        spec = self.entries[name]
        chezmoi = harness.find_binary("chezmoi")
        if chezmoi is None:
            return StateChangeOutcome(changed=False, status="hard_fail", message="chezmoi not found — the [url.chezmoi] section must run before [chezmoi].")
        source = self._source_path()
        harness.write_if_changed(self._config_path(), self._config_bytes(), note="chezmoi config")
        try:
            if not self._is_cloned():
                shell.stream([str(chezmoi), "init", "--source", str(source), spec.repo], note="chezmoi init")
            self._setup_capture()
        except subprocess.CalledProcessError as exc:
            return StateChangeOutcome(changed=False, status="hard_fail", message=f"chezmoi failed: {exc}")
        return StateChangeOutcome(changed=True)
