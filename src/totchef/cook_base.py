"""Shared contract for totchef cooks: a cook probes and acts but holds no diff logic (chef owns the diff); VersionedCook covers versioned packages, StateCook desired-state resources. See CLAUDE.md."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Literal, cast

from pydantic import BaseModel, ConfigDict

Status = Literal["ok", "soft_fail", "hard_fail"]


class EntrySpec(BaseModel):
    """Base for every cook's recipe-entry schema; `extra='forbid'` fails a typo'd recipe key instead of silently ignoring it. Carries the `pre_hook` guard / `post_hook` pair every cook honors — a versioned cook gates/refreshes the whole section, a state cook gates/refreshes each resource."""

    model_config = ConfigDict(extra="forbid")

    pre_hook: str | None = None
    post_hook: str | None = None


def chain_hooks(*commands: str | None) -> str | None:
    """Join present shell commands with `&&` (None if none) so an intrinsic hook composes with a recipe-declared one; a non-zero link short-circuits a pre_hook guard."""
    present = [command for command in commands if command]
    return " && ".join(present) if present else None


class PackagesConfig(EntrySpec):
    """Schema shared by the plain package-list sections (cargo, uv, apt_pkg, snap)."""

    packages: list[str] = []


@dataclass(frozen=True)
class SyncOutcome:
    """Outcome of a VersionedCook.sync (or any cook-level act); expected failures land here as a status, only bugs raise."""

    status: Status = "ok"
    message: str = ""


@dataclass(frozen=True)
class StateChangeOutcome:
    """Outcome of a StateCook.apply_resource for one resource."""

    changed: bool
    status: Status = "ok"
    message: str = ""


@dataclass(frozen=True)
class ReportRow:
    """One row of the end-of-run report, assembled by chef. `before`/`current`/`latest` form a past/present/future triple: pre-run state (or `—` in a plan), state right now (post-sync on `up`), upgrade target."""

    name: str
    before: str
    current: str
    latest: str
    action: str
    changed: bool
    status: Status = "ok"


@dataclass
class CookResult:
    """Everything chef needs from one cook — status, report rows, optional message — pickled back from a forked child, so plain dataclasses only."""

    cook: str
    status: Status
    rows: list[ReportRow] = field(default_factory=list)
    message: str = ""


class CookBase:
    """Base for every cook; an always-root `<section>_root_cook.py` sets `needs_root = True` (else least privilege)."""

    needs_root: bool = False
    entry_model: ClassVar[type[EntrySpec] | None] = None

    def __init__(self, section: dict) -> None:
        self.section = section

    @property
    def unit_count(self) -> int:
        """Discrete units of work this cook represents — one by default, weighting its scheduler pull; a versioned cook overrides with its package count."""
        return 1


class VersionedCook(CookBase):
    @property
    def unit_count(self) -> int:
        return len(self.list_requested())

    def get_hooks(self) -> tuple[str | None, str | None]:
        """The section-level (pre_hook, post_hook): the pre_hook gates the whole sync, the post_hook fires once after a change. None unless the cook reads them off its entry_model."""
        return (None, None)

    def list_requested(self) -> list[str]:
        raise NotImplementedError

    def list_installed(self) -> dict[str, str]:
        raise NotImplementedError

    def find_latest(self, names: list[str]) -> dict[str, str | None]:
        raise NotImplementedError

    def sync(self, to_install: list[str], to_upgrade: list[str]) -> SyncOutcome:
        raise NotImplementedError


class PackageListCook(VersionedCook):
    """VersionedCook over a plain `packages = [...]` section (cargo, uv, snap, apt_pkg), with a no-op `find_latest` a manager with a cheap candidate (apt) overrides."""

    entry_model = PackagesConfig

    def __init__(self, section: dict) -> None:
        super().__init__(section)
        config = PackagesConfig.model_validate(section)
        self.packages = config.packages
        self.hooks = (config.pre_hook, config.post_hook)

    def list_requested(self) -> list[str]:
        return self.packages

    def get_hooks(self) -> tuple[str | None, str | None]:
        return self.hooks

    def find_latest(self, names: list[str]) -> dict[str, str | None]:
        return dict.fromkeys(names)


class StateCook[EntryModel: EntrySpec](CookBase):
    """Desired-state cook over a subtable section; the base serves `list_resources` and default `get_hooks`, subclasses implement the get_current_state/get_desired_state/apply_resource diff."""

    def __init__(self, section: dict) -> None:
        super().__init__(section)
        model = self.entry_model
        assert model is not None, f"{type(self).__name__} must set entry_model"
        self.entries: dict[str, EntryModel] = {name: cast("EntryModel", model.model_validate(raw)) for name, raw in section.items()}

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
    """A StateCook whose diff is a content hash — sha256 of the on-disk file vs the rendered bytes; subclasses supply `_target_path` and `_render` and keep their own `apply_resource`."""

    _unrendered_label = "absent"

    def _target_path(self, name: str) -> Path:
        raise NotImplementedError

    def _render(self, name: str) -> bytes | None:
        raise NotImplementedError

    def get_current_state(self) -> dict[str, str]:
        states: dict[str, str] = {}
        for name in self.entries:
            path = self._target_path(name)
            states[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"
        return states

    def get_desired_state(self) -> dict[str, str]:
        states: dict[str, str] = {}
        for name in self.entries:
            content = self._render(name)
            states[name] = hashlib.sha256(content).hexdigest() if content is not None else self._unrendered_label
        return states
