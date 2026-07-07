"""Shared base for the PATH-install cooks ([usr_local_bin]/[usr_local_sbin]/[local_bin]) — install a bundled command (any language, even a compiled binary) as a 0755 executable named after its source stem; an omitted `source` defaults to the bundled file named after the entry. An embedded `__version__` marker is the diff key, and the version/help contract is read off the file's bytes (the command is never executed)."""

import re
from pathlib import Path
from typing import ClassVar

from pydantic import ValidationInfo, model_validator

from totchef import harness
from totchef.cook_base import EntrySpec, StateChangeOutcome, StateCook, get_entry_name

EXECUTABLE_MODE = 0o755
VERSION_MARKER_PATTERN = re.compile(r'__version__\s*=\s*"([^"]+)"')
HELP_EVIDENCE_PATTERN = re.compile(r"^\s*(?:import|from)\s+(?:argparse|click|typer)\b|--help", re.MULTILINE)


def find_embedded_version(file_text: str) -> str | None:
    marker = VERSION_MARKER_PATTERN.search(file_text)
    return marker.group(1) if marker else None


def find_contract_problems(command_path: Path) -> list[str]:
    """The static checks a PATH-installed command must pass — embed a `__version__` marker, offer `--version` and `--help` — collected as readable problems (empty == compliant), read off the file's bytes without executing it."""
    if not command_path.is_file():
        return [f"bundled command {command_path.name} not found under {command_path.parent}"]
    file_text = command_path.read_text(errors="replace")
    problems: list[str] = []
    if find_embedded_version(file_text) is None:
        problems.append('command must embed __version__ = "<version>" (a constant in any language, or a string baked into a binary)')
    if "--version" not in file_text:
        problems.append("command must offer --version")
    if not HELP_EVIDENCE_PATTERN.search(file_text):
        problems.append("command must offer --help (argparse/click/typer, or handle it explicitly)")
    return problems


class BinEntry(EntrySpec):
    source: str

    @model_validator(mode="before")
    @staticmethod
    def _default_source_to_bundled(entry_input: object, info: ValidationInfo) -> object:
        if isinstance(entry_input, dict) and "source" not in entry_input:
            return {**entry_input, "source": harness.resolve_bundled_source(get_entry_name(info))}
        return entry_input

    @model_validator(mode="after")
    def _command_honors_contract(self) -> "BinEntry":
        if problems := find_contract_problems(harness.files_dir() / self.source):
            raise ValueError("; ".join(problems))
        return self


class BinCommandCook(StateCook[BinEntry]):
    """StateCook whose diff key is the command's embedded `__version__`: an absent, unversioned, or differently-versioned install is rewritten; equal versions leave the file alone. Subclasses pin `bin_dir`."""

    entry_model = BinEntry
    bin_dir: ClassVar[str]

    def _target_path(self, name: str) -> Path:
        return Path(self.bin_dir).expanduser() / Path(self.entries[name].source).stem

    def get_current_state(self) -> dict[str, str]:
        states: dict[str, str] = {}
        for name in self.entries:
            target = self._target_path(name)
            states[name] = (find_embedded_version(target.read_text(errors="replace")) or "unversioned") if target.is_file() else "absent"
        return states

    def get_desired_state(self) -> dict[str, str]:
        states: dict[str, str] = {}
        for name, entry in self.entries.items():
            states[name] = find_embedded_version((harness.files_dir() / entry.source).read_text(errors="replace")) or "unversioned"
        return states

    def apply_resource(self, name: str) -> StateChangeOutcome:
        command_bytes = (harness.files_dir() / self.entries[name].source).read_bytes()
        changed = harness.write_if_changed(self._target_path(name), command_bytes, EXECUTABLE_MODE, note=name)
        return StateChangeOutcome(changed=changed)
