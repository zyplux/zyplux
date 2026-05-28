"""StateCook for [desktop.<app>] — per-user .desktop Exec= overrides (env prefix + --switches + --enable-features) under ~/.local/share/applications, diffed by content hash. Runs as the invoking user."""

from pathlib import Path

from totchef.cook_base import FileStateCook, StateChangeOutcome, EntrySpec, chain_hooks
from totchef.harness import logger, write_if_changed

# Refresh KDE's ksycoca so the launcher stops spawning apps with the stale Exec
# line; tolerant of non-KDE systems where kbuildsycoca6 is absent.
KSYCOCA_REFRESH = "command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 --noincremental || true"


def rewrite_exec_line(
    exec_value: str,
    env: dict[str, str],
    features: list[str],
    switches: list[str],
) -> str:
    """Idempotent rewrite of a .desktop Exec= value with env prefix, --<switch>es, and --enable-features, inserting new args before trailing field codes (%U/%u/%F/%f)."""
    tokens = exec_value.split()

    if tokens and tokens[0] == "env":
        cursor = 1
        while cursor < len(tokens) and "=" in tokens[cursor] and not tokens[cursor].startswith("-"):
            cursor += 1
        tokens = tokens[cursor:]

    # Switches may be bare ("enable-foo") or key=value ("render-node-override=/x"); dedupe
    # by key so a value change in recipe.toml replaces the old token instead of duplicating.
    managed_keys = {f"--{switch.split('=', 1)[0]}" for switch in switches}
    tokens = [
        token for token in tokens if not token.startswith("--enable-features=") and not any(token == key or token.startswith(key + "=") for key in managed_keys)
    ]

    insert_at = next(
        (index for index, token in enumerate(tokens) if len(token) == 2 and token.startswith("%")),
        len(tokens),
    )
    for switch in switches:
        tokens.insert(insert_at, f"--{switch}")
        insert_at += 1
    if features:
        tokens.insert(insert_at, f"--enable-features={','.join(features)}")

    if env:
        tokens = ["env", *(f"{k}={v}" for k, v in env.items()), *tokens]

    return " ".join(tokens)


class DesktopEntry(EntrySpec):
    desktop: str
    features: list[str] = []
    switches: list[str] = []
    env: dict[str, str] = {}


class DesktopCook(FileStateCook[DesktopEntry]):
    entry_model = DesktopEntry
    _unrendered_label = "(no source)"

    def _target_path(self, name: str) -> Path:
        system_desktop = Path(self.entries[name].desktop)
        return Path.home() / ".local/share/applications" / system_desktop.name

    def _render(self, name: str) -> bytes | None:
        app = self.entries[name]
        system_desktop = Path(app.desktop)
        if not system_desktop.exists():
            return None
        env = app.env
        features = app.features
        switches = app.switches
        lines = []
        for line in system_desktop.read_text().splitlines():
            if line.startswith("Exec="):
                lines.append("Exec=" + rewrite_exec_line(line[5:], env, features, switches))
            else:
                lines.append(line)
        return ("\n".join(lines) + "\n").encode()

    def get_hooks(self, name: str) -> tuple[str | None, str | None]:
        app = self.entries[name]
        return (app.pre_hook, chain_hooks(app.post_hook, KSYCOCA_REFRESH))

    def apply_resource(self, name: str) -> StateChangeOutcome:
        content = self._render(name)
        if content is None:
            return StateChangeOutcome(
                changed=False,
                message=f"{self.entries[name].desktop} not found; install the package first.",
            )
        changed = write_if_changed(self._target_path(name), content, note=name)
        if changed:
            logger.info("Restart the app to apply the new Exec= line.")
        return StateChangeOutcome(changed=changed)
