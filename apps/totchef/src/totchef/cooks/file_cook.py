"""StateCook for [file.<name>] — install a file with exact content (inline `content`, a bundled `source` from the recipe's sibling totchef_files/, or with neither set the bundled file named after the entry), diffed by content hash so a `post_hook` fires only on change. `path` expands `~` for per-user installs. Privilege-agnostic; recipe.toml grants root per entry."""

from pathlib import Path

from pydantic import ValidationInfo, model_validator

from totchef import harness
from totchef.cook_base import FileStateCook, StateChangeOutcome, EntrySpec, get_entry_name


class FileEntry(EntrySpec):
    path: str
    source: str | None = None
    content: str | None = None
    mode: str = "0644"

    @model_validator(mode="after")
    def _resolve_body(self, info: ValidationInfo) -> "FileEntry":
        if self.source is not None and self.content is not None:
            raise ValueError("set `source` or `content`, not both")
        if self.source is None and self.content is None:
            self.source = harness.resolve_bundled_source(get_entry_name(info))
        return self


class FileCook(FileStateCook[FileEntry]):
    entry_model = FileEntry

    def _target_path(self, name: str) -> Path:
        return Path(self.entries[name].path).expanduser()

    def _render(self, name: str) -> bytes:
        entry = self.entries[name]
        if entry.source is not None:
            return (harness.files_dir() / entry.source).read_bytes()
        return (entry.content or "").encode()

    def _parse_mode(self, name: str) -> int:
        return int(self.entries[name].mode, 8)

    def apply_resource(self, name: str) -> StateChangeOutcome:
        changed = harness.write_if_changed(
            self._target_path(name),
            self._render(name),
            self._parse_mode(name),
            note=name,
        )
        return StateChangeOutcome(changed=changed)
