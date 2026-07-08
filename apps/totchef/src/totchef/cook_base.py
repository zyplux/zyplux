"""Shared contract for totchef cooks: probes and acts (chef owns the diff); VersionedCook packages, StateCook state."""

import hashlib
import stat
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal, cast, override

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator

if TYPE_CHECKING:
    from pathlib import Path

    from totchef.recipe_types import RecipeConfig

Status = Literal["ok", "soft_fail", "hard_fail"]


class RemoveHowWithoutProbeError(ValueError):
    """`remove_how` was declared without the `remove_when` probe that would ever unlock it."""


class EntrySpec(BaseModel):
    """Base for every cook's entry schema (extra=forbid rejects typos); carries pre/post_hook, remove_when/-how."""

    model_config = ConfigDict(extra="forbid")

    pre_hook: str | None = None
    post_hook: str | None = None
    remove_when: str | None = None
    remove_how: str | None = None

    @model_validator(mode="after")
    def validate_remove_how_has_a_condition(self) -> EntrySpec:
        """`remove_how` is the instruction `remove_when` unlocks; without the probe it would never surface."""
        if self.remove_how and not self.remove_when:
            failure = (
                "`remove_how` has no `remove_when` — declare the probe that makes this entry "
                "removable, or drop `remove_how`"
            )
            raise RemoveHowWithoutProbeError(failure)
        return self


def get_entry_name(info: ValidationInfo) -> str | None:
    """The recipe entry's name, handed to validation as context so a validator can default fields off it."""
    return (info.context or {}).get("entry_name")


def chain_hooks(*commands: str | None) -> str | None:
    """Join present shell commands with && (None if none), so hooks compose; a non-zero link short-circuits."""
    present = [command for command in commands if command]
    return " && ".join(present) if present else None


class PackagesConfig(EntrySpec):
    """Schema shared by the plain package-list sections (cargo, uv, apt_pkg, snap)."""

    packages: list[str] = []


@dataclass(frozen=True)
class SyncOutcome:
    """Outcome of VersionedCook.sync; expected failures land as a status, only bugs raise; delayed_message follows."""

    status: Status = "ok"
    message: str = ""
    delayed_message: str = ""


@dataclass(frozen=True)
class StateChangeOutcome:
    """Outcome of StateCook.apply_resource; delayed_message is an operator follow-up repeated after the report."""

    changed: bool
    status: Status = "ok"
    message: str = ""
    delayed_message: str = ""


@dataclass(frozen=True)
class ReportRow:
    """One end-of-run report row, assembled by chef. before/current/latest: pre-run state, state now, upgrade target."""

    name: str
    before: str
    current: str
    latest: str
    action: str
    changed: bool
    status: Status = "ok"


@dataclass
class CookResult:
    """Everything chef needs from one cook — status, rows, message, delayed follow-ups — JSON-encoded from a child."""

    cook: str
    status: Status
    rows: list[ReportRow] = field(default_factory=list)
    message: str = ""
    delayed_messages: list[str] = field(default_factory=list)


class CookBase:
    """Base for every cook; an always-root `<section>_root_cook.py` sets needs_root=True; entry_keyed picks shape."""

    needs_root: bool = False
    entry_model: ClassVar[type[EntrySpec] | None] = None
    entry_keyed: ClassVar[bool] = False

    def __init__(self, section: RecipeConfig) -> None:
        self.section = section

    @property
    def unit_count(self) -> int:
        """Discrete units of work this cook represents — one by default; versioned cooks override with package count."""
        return 1


class VersionedCook(CookBase):
    @property
    @override
    def unit_count(self) -> int:
        return len(self.list_requested())

    @staticmethod
    def get_hooks() -> tuple[str | None, str | None]:
        """The section-level (pre_hook, post_hook); pre_hook gates the sync, post_hook fires after a change."""
        return (None, None)

    def list_requested(self) -> list[str]:
        raise NotImplementedError

    def list_installed(self) -> dict[str, str]:
        raise NotImplementedError

    def find_latest(self, names: list[str]) -> dict[str, str | None]:
        raise NotImplementedError

    @staticmethod
    def list_reportable(requested: list[str], _installed_after: dict[str, str], /) -> list[str]:
        """Row keys for the post-sync report — requested names by default; overridden by cooks splitting finer items."""
        return requested

    def sync(self, to_install: list[str], to_upgrade: list[str]) -> SyncOutcome:
        raise NotImplementedError


class PackageListCook(VersionedCook):
    """VersionedCook over a plain packages=[...] section (cargo, uv, snap, apt_pkg); find_latest is usually a no-op."""

    entry_model = PackagesConfig

    def __init__(self, section: RecipeConfig) -> None:
        super().__init__(section)
        config = PackagesConfig.model_validate(section)
        self.packages = config.packages
        self.hooks = (config.pre_hook, config.post_hook)

    @override
    def list_requested(self) -> list[str]:
        return self.packages

    @override
    def get_hooks(self) -> tuple[str | None, str | None]:
        return self.hooks

    @override
    def find_latest(self, names: list[str]) -> dict[str, str | None]:
        return dict.fromkeys(names)


class EntryModelNotSetError(TypeError):
    """A StateCook subclass omitted the `entry_model` class attribute every concrete cook must declare."""


class StateCook[EntryModel: EntrySpec](CookBase):
    """Desired-state cook over a subtable section; subclasses implement get/desired_state and apply_resource."""

    entry_keyed = True

    def __init__(self, section: RecipeConfig) -> None:
        super().__init__(section)
        model = self.entry_model
        if model is None:
            failure = f"{type(self).__name__} must set entry_model"
            raise EntryModelNotSetError(failure)
        self.entries: dict[str, EntryModel] = {
            name: cast("EntryModel", model.model_validate(raw, context={"entry_name": name}))
            for name, raw in section.items()
        }

    def list_resources(self) -> list[str]:
        return list(self.entries)

    def get_current_state(self) -> dict[str, str]:
        raise NotImplementedError

    def get_desired_state(self) -> dict[str, str]:
        raise NotImplementedError

    def get_hooks(self, name: str) -> tuple[str | None, str | None]:
        entry = self.entries[name]
        return (entry.pre_hook, entry.post_hook)

    def apply_resource(self, name: str) -> StateChangeOutcome:
        raise NotImplementedError


class FileStateCook[EntryModel: EntrySpec](StateCook[EntryModel]):
    """A StateCook diffing by content hash — sha256 of file vs rendered bytes; subclasses supply target/render."""

    _unrendered_label = "absent"

    def _target_path(self, name: str) -> Path:
        raise NotImplementedError

    def _render(self, name: str) -> bytes | None:
        raise NotImplementedError

    def _mode(self, name: str) -> int | None:
        """The declared target mode to diff against, read off the entry's own `mode` field if it has one."""
        mode = getattr(self.entries[name], "mode", None)
        return int(mode, 8) if isinstance(mode, str) else None

    @override
    def get_current_state(self) -> dict[str, str]:
        states: dict[str, str] = {}
        for name in self.entries:
            path = self._target_path(name)
            if not path.exists():
                states[name] = "absent"
                continue
            raw = path.read_bytes()
            wanted_mode = self._mode(name)
            actual_mode = stat.S_IMODE(path.stat().st_mode)
            mode_drifted = wanted_mode is not None and actual_mode != wanted_mode
            # A drifted mode must still force this entry to diff as "differs" against a pure content
            # digest, without masking a genuine content difference behind a mode-only message — so it's
            # mixed into the hashed bytes rather than replacing the digest.
            digest_input = raw + b"\0mode-drift" if mode_drifted else raw
            states[name] = hashlib.sha256(digest_input).hexdigest()
        return states

    @override
    def get_desired_state(self) -> dict[str, str]:
        states: dict[str, str] = {}
        for name in self.entries:
            content = self._render(name)
            states[name] = hashlib.sha256(content).hexdigest() if content is not None else self._unrendered_label
        return states
