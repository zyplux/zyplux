(
    """StateCook for [settings.<app>] — merge a `settings_env` block into the `env` key of a JSON settings """
    """file, preserving other keys, diffed by merged-JSON hash. Runs as the invoking user."""
)

import json
from pathlib import Path
from typing import Any, override

from pydantic import Field

from totchef.cook_base import EntrySpec, FileStateCook, StateChangeOutcome
from totchef.harness import write_if_changed


class SettingsEntry(EntrySpec):
    settings_json: str
    settings_env: dict[str, str] = Field(default_factory=dict)


class SettingsCook(FileStateCook[SettingsEntry]):
    entry_model = SettingsEntry
    _unrendered_label = "invalid-json"

    @override
    def _target_path(self, name: str) -> Path:
        return Path.home() / self.entries[name].settings_json

    @override
    def _render(self, name: str) -> bytes | None:
        target = self._target_path(name)
        env_overrides = self.entries[name].settings_env
        if not target.exists():
            existing: dict[str, Any] = {}
        else:
            try:
                parsed = json.loads(target.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
            if not isinstance(parsed, dict) or not isinstance(parsed.get("env", {}), dict):
                return None
            existing = parsed
        merged = {**existing, "env": {**existing.get("env", {}), **env_overrides}}
        return (json.dumps(merged, indent=2) + "\n").encode()

    @override
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
