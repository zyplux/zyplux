"""StateCook for [chromium_flags.<app>] — GPU-flag injection into a Chromium `Local State` JSON or an Electron argv.json, picked per app by marker and diffed by rendered-JSON hash. Runs as the invoking user."""

import json
from pathlib import Path

from pydantic import model_validator

from totchef.cook_base import FileStateCook, StateChangeOutcome, EntrySpec, chain_hooks
from totchef.harness import logger, write_if_changed


def _strip_json_comments(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))


class ChromiumFlagsEntry(EntrySpec):
    local_state: str | None = None
    local_state_flags: list[str] = []
    argv_json: str | None = None
    argv: dict[str, str | bool] = {}
    features: list[str] = []
    process_name: str | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "ChromiumFlagsEntry":
        if (self.local_state is None) == (self.argv_json is None):
            raise ValueError("set exactly one of `local_state` or `argv_json`")
        return self


class ChromiumFlagsCook(FileStateCook[ChromiumFlagsEntry]):
    entry_model = ChromiumFlagsEntry
    _unrendered_label = "(no base file)"

    def _target_path(self, name: str) -> Path:
        app = self.entries[name]
        return Path.home() / (app.local_state or app.argv_json or "")

    def _render(self, name: str) -> bytes | None:
        """Desired file bytes, or None when there is no base file or it is invalid JSON (apply_resource soft-fails the latter); returns on-disk bytes verbatim when no flag changes, so chef skips the entry."""
        app = self.entries[name]
        target = self._target_path(name)
        if app.local_state is not None:
            flags = app.local_state_flags
            if not target.exists():
                return None
            raw = target.read_bytes()
            if not flags:
                return raw
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return None
            experiments = data.setdefault("browser", {}).setdefault("enabled_labs_experiments", [])
            merged = sorted(set(experiments) | set(flags))
            if set(merged) == set(experiments):
                return raw
            data["browser"]["enabled_labs_experiments"] = merged
            return json.dumps(data, indent=2).encode()

        # argv_json (Electron)
        argv: dict[str, str | bool] = dict(app.argv)
        features = app.features
        if features:
            argv["enable-features"] = ",".join(features)
        existing: dict = {}
        if target.exists():
            stripped = _strip_json_comments(target.read_text())
            if stripped.strip():
                try:
                    existing = json.loads(stripped)
                except json.JSONDecodeError:
                    return None
        merged = {**existing, **argv}
        return (json.dumps(merged, indent=2) + "\n").encode()

    def get_hooks(self, name: str) -> tuple[str | None, str | None]:
        app = self.entries[name]
        # Skip the Local State write while the browser runs (it would race the
        # browser's own write); `! pgrep` exits non-zero when found, so chef skips.
        guard = f"! pgrep -x {app.process_name or name} >/dev/null" if app.local_state is not None else None
        return (chain_hooks(guard, app.pre_hook), app.post_hook)

    def apply_resource(self, name: str) -> StateChangeOutcome:
        content = self._render(name)
        if content is None:
            target = self._target_path(name)
            if target.exists():
                return StateChangeOutcome(
                    changed=False,
                    status="soft_fail",
                    message=f"{target}: invalid JSON, leaving as-is.",
                )
            return StateChangeOutcome(
                changed=False,
                message=f"{target} not found; launch the app once, then re-run.",
            )
        changed = write_if_changed(self._target_path(name), content, note=name)
        if changed:
            logger.info(f"{name}: restart the app to apply the new flags.")
        return StateChangeOutcome(changed=changed)
