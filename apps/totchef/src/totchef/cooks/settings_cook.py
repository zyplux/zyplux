"""StateCook for [settings.<app>] — merge a `settings_env` block into the `env` key of a JSON settings file, preserving other keys, diffed by merged-JSON hash. Runs as the invoking user."""

import json
from pathlib import Path

from totchef.cook_base import FileStateCook, StateChangeOutcome, EntrySpec
from totchef.harness import write_if_changed


class SettingsEntry(EntrySpec):
    settings_json: str
    settings_env: dict[str, str] = {}


class SettingsCook(FileStateCook[SettingsEntry]):
    entry_model = SettingsEntry
    _unrendered_label = "invalid-json"

    def _target_path(self, name: str) -> Path:
        return Path.home() / self.entries[name].settings_json

    def _render(self, name: str) -> bytes | None:
        target = self._target_path(name)
        env_overrides = self.entries[name].settings_env
        try:
            existing: dict = json.loads(target.read_text()) if target.exists() else {}
        except json.JSONDecodeError:
            return None
        merged = {**existing, "env": {**existing.get("env", {}), **env_overrides}}
        return (json.dumps(merged, indent=2) + "\n").encode()

    def apply_resource(self, name: str) -> StateChangeOutcome:
        content = self._render(name)
        if content is None:
            return StateChangeOutcome(
                changed=False,
                status="soft_fail",
                message=f"{self._target_path(name)}: invalid JSON, leaving as-is.",
            )
        changed = write_if_changed(self._target_path(name), content, note=name)
        return StateChangeOutcome(changed=changed)
