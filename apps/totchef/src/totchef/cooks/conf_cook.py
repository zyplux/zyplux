"""StateCook for [conf.<name>] — own specific lines of a config file another package ships: each declared line is keyed on the text before `=` (the whole line when there is none), replacing same-key lines in place, appending missing ones, and leaving the rest of the file untouched. Creates `target` when absent; diffed by content hash so a `post_hook` fires only on change. Privilege-agnostic; recipe.toml grants root per entry."""

from pathlib import Path
from typing import override

from pydantic import Field, model_validator

from totchef import harness
from totchef.cook_base import EntrySpec, FileStateCook, StateChangeOutcome


class ConfEntry(EntrySpec):
    target: str
    line: str | None = None
    lines: list[str] | None = Field(None, min_length=1)

    @model_validator(mode="after")
    def _require_exactly_one_form(self) -> "ConfEntry":
        if self.line is not None and self.lines is not None:
            raise ValueError("set `line` or `lines`, not both")
        if self.line is None and self.lines is None:
            raise ValueError("set `line` or `lines`")
        return self

    @property
    def desired_lines(self) -> list[str]:
        return [self.line] if self.line is not None else self.lines or []


def get_line_key(line: str) -> str:
    return line.split("=", 1)[0].strip()


def ensure_lines(text: str, desired_lines: list[str]) -> str:
    rows = text.splitlines()
    for desired in desired_lines:
        key = get_line_key(desired)
        if any(get_line_key(row) == key for row in rows):
            rows = [desired if get_line_key(row) == key else row for row in rows]
        else:
            rows.append(desired)
    return "\n".join(rows) + "\n"


class ConfCook(FileStateCook[ConfEntry]):
    entry_model = ConfEntry

    @override
    def _target_path(self, name: str) -> Path:
        return Path(self.entries[name].target).expanduser()

    @override
    def _render(self, name: str) -> bytes:
        path = self._target_path(name)
        text = path.read_text() if path.exists() else ""
        return ensure_lines(text, self.entries[name].desired_lines).encode()

    @override
    def apply_resource(self, name: str) -> StateChangeOutcome:
        path = self._target_path(name)
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
        changed = harness.write_if_changed(path, self._render(name), mode, note=name)
        return StateChangeOutcome(changed=changed)
