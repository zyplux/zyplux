"""StateCook for [file.<name>] — install a file with exact content (inline or bundled under totchef/files/), diffed by content hash so a `post_hook` fires only on change. Privilege-agnostic; recipe.toml grants root per entry."""

from pathlib import Path

from pydantic import model_validator

from totchef.cook_base import FileStateCook, StateChangeOutcome, EntrySpec
from totchef.harness import FILES_DIR, write_if_changed


class FileEntry(EntrySpec):
    path: str
    source: str | None = None
    content: str | None = None
    mode: str = "0644"

    @model_validator(mode="after")
    def _exactly_one_body(self) -> "FileEntry":
        if (self.source is None) == (self.content is None):
            raise ValueError("set exactly one of `source` or `content`")
        return self


class FileCook(FileStateCook[FileEntry]):
    entry_model = FileEntry

    def _target_path(self, name: str) -> Path:
        return Path(self.entries[name].path)

    def _render(self, name: str) -> bytes:
        entry = self.entries[name]
        if entry.source is not None:
            return (FILES_DIR / entry.source).read_bytes()
        return (entry.content or "").encode()

    def _parse_mode(self, name: str) -> int:
        return int(self.entries[name].mode, 8)

    def apply_resource(self, name: str) -> StateChangeOutcome:
        changed = write_if_changed(
            self._target_path(name),
            self._render(name),
            self._parse_mode(name),
            note=name,
        )
        return StateChangeOutcome(changed=changed)
