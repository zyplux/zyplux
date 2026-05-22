"""
Idempotent per-app config from apps_config.toml.

Dispatches per section on which key(s) are present:
- `desktop`       — writes a per-user .desktop override with env prefix +
                    --enable-features + --<switch>es.
- `local_state`   — patches a Chromium-family `Local State` for
                    brave://flags-style UI mirroring.
- `argv_json`     — merges an Electron-style argv.json for allowlisted
                    Chromium flags (e.g. VS Code).
- `settings_json` — merges an `env` block into a JSON settings file
                    (e.g. ~/.claude/settings.json's env field).

Refreshes KDE's ksycoca cache if any .desktop was rewritten — without it
the launcher keeps spawning apps with the previously-cached Exec line.
"""

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

from loguru import logger

from harness import (
    SRC_DIR,
    get_invoking_user,
    reexec_under_sudo,
    start_log_tee,
)

SCRIPT = Path(__file__).resolve()
APPS_CONFIG_TOML = SRC_DIR / "apps_config.toml"


def rewrite_exec_line(
    exec_value: str,
    env: dict[str, str],
    features: list[str],
    switches: list[str],
) -> str:
    """Idempotent rewrite of a .desktop Exec= value with env prefix, --<switch>s, and
    --enable-features. New args insert before trailing field codes (%U, %u, %F, %f)."""
    tokens = exec_value.split()

    if tokens and tokens[0] == "env":
        i = 1
        while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("-"):
            i += 1
        tokens = tokens[i:]

    # Switches may be bare ("enable-foo") or key=value ("render-node-override=/x"); dedupe
    # by key so a value change in apps_config.toml replaces the old token instead of duplicating.
    managed_keys = {f"--{s.split('=', 1)[0]}" for s in switches}
    tokens = [
        t
        for t in tokens
        if not t.startswith("--enable-features=")
        and not any(t == k or t.startswith(k + "=") for k in managed_keys)
    ]

    insert_at = next(
        (i for i, t in enumerate(tokens) if len(t) == 2 and t.startswith("%")),
        len(tokens),
    )
    for sw in switches:
        tokens.insert(insert_at, f"--{sw}")
        insert_at += 1
    if features:
        tokens.insert(insert_at, f"--enable-features={','.join(features)}")

    if env:
        tokens = ["env", *(f"{k}={v}" for k, v in env.items()), *tokens]

    return " ".join(tokens)


def write_desktop_override(
    system_desktop: Path,
    env: dict[str, str],
    features: list[str],
    switches: list[str],
    uid: int,
    gid: int,
    home: Path,
) -> bool:
    """Per-user .desktop override: copy system .desktop, rewrite each Exec= line
    with env prefix + --<switch>es + --enable-features, write to ~/.local/share/
    applications/ chowned to the invoking user. Idempotent. Returns True if a
    write happened (so the caller knows to refresh ksycoca)."""
    if not system_desktop.exists():
        logger.warning(
            f"{system_desktop} not found; skipping .desktop override "
            "(install package via configure_with_apt.py first)"
        )
        return False

    new_lines = []
    rewritten = 0
    for line in system_desktop.read_text().splitlines():
        if line.startswith("Exec="):
            new_lines.append(
                "Exec=" + rewrite_exec_line(line[5:], env, features, switches)
            )
            rewritten += 1
        else:
            new_lines.append(line)
    new_text = "\n".join(new_lines) + "\n"

    dst_dir = home / ".local/share/applications"
    dst = dst_dir / system_desktop.name
    dst_dir.mkdir(parents=True, exist_ok=True)
    os.chown(dst_dir, uid, gid)

    if dst.exists() and dst.read_text() == new_text:
        logger.info(f"Unchanged: {dst}")
        return False

    logger.info(f"Writing  : {dst}  ({rewritten} Exec= line(s) rewritten)")
    dst.write_text(new_text)
    os.chown(dst, uid, gid)
    dst.chmod(0o644)
    return True


def patch_chromium_local_state(
    local_state: Path,
    flags: list[str],
    process_name: str,
    uid: int,
    gid: int,
) -> bool:
    """Add `flags` to browser.enabled_labs_experiments in a Chromium-family Local
    State JSON. Skips if the browser is currently running (would race the write).
    Returns True if a write happened."""
    if not flags:
        return False
    if not local_state.exists():
        logger.warning(
            f"{local_state} not found; skipping Local State patch "
            f"(launch {process_name} once, then re-run)"
        )
        return False

    if (
        subprocess.run(["pgrep", "-x", process_name], capture_output=True).returncode
        == 0
    ):
        logger.warning(
            f"{process_name} is running; skipping Local State patch (would race the write)."
        )
        logger.warning(
            f"Quit {process_name} and re-run configure_apps.py to sync flag UI state."
        )
        return False

    local_state_json = json.loads(local_state.read_text())
    experiments = local_state_json.setdefault("browser", {}).setdefault(
        "enabled_labs_experiments", []
    )
    existing_flags = set(experiments)
    merged_flags = existing_flags | set(flags)
    if merged_flags == existing_flags:
        logger.info(f"Local State already has all {len(flags)} flag entries")
        return False

    local_state_json["browser"]["enabled_labs_experiments"] = sorted(merged_flags)
    local_state.write_text(json.dumps(local_state_json, indent=2))
    os.chown(local_state, uid, gid)
    logger.info(f"Local State: added {sorted(merged_flags - existing_flags)}")
    return True


def merge_electron_argv_json(
    path: Path, argv_overrides: dict, uid: int, gid: int
) -> bool:
    """Merge `argv_overrides` into an Electron-style argv.json, preserving any
    other keys the user added (e.g. crash-reporter-id). VS Code ships the default
    file full of // comments — those get stripped on first managed write.
    Returns True if a write happened."""
    if not argv_overrides:
        return False
    existing: dict = {}
    if path.exists():
        no_comments = "\n".join(
            ln
            for ln in path.read_text().splitlines()
            if not ln.lstrip().startswith("//")
        )
        if no_comments.strip():
            existing = json.loads(no_comments)
    merged = {**existing, **argv_overrides}
    new_text = json.dumps(merged, indent=2) + "\n"

    if path.exists() and path.read_text() == new_text:
        logger.info(f"Unchanged: {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text)
    os.chown(path.parent, uid, gid)
    os.chown(path, uid, gid)
    logger.info(f"Writing  : {path}  (argv keys merged: {sorted(argv_overrides)})")
    return True


def merge_settings_json_env(
    path: Path, env_overrides: dict[str, str], uid: int, gid: int
) -> bool:
    """Merge `env_overrides` into the top-level `env` key of a JSON settings
    file (e.g. ~/.claude/settings.json), preserving every other key the user
    has set. Existing env entries with the same name are overridden — the TOML
    declares the desired state. Returns True if a write happened."""
    if not env_overrides:
        return False
    existing: dict = {}
    if path.exists():
        existing = json.loads(path.read_text())
    new_env = {**existing.get("env", {}), **env_overrides}
    merged = {**existing, "env": new_env}
    new_text = json.dumps(merged, indent=2) + "\n"

    if path.exists() and path.read_text() == new_text:
        logger.info(f"Unchanged: {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text)
    os.chown(path.parent, uid, gid)
    os.chown(path, uid, gid)
    logger.info(f"Writing  : {path}  (env keys merged: {sorted(env_overrides)})")
    return True


def configure_app(
    app_name: str,
    app_config: dict,
    shared_env: dict[str, str],
    chromium_features: list[str],
    uid: int,
    gid: int,
    home: Path,
) -> tuple[bool, bool]:
    """Returns (any_change, desktop_change). desktop_change is tracked
    separately because only .desktop writes need a ksycoca refresh."""
    logger.info(f"Configuring {app_name}")
    env = {**shared_env, **app_config.get("env", {})}
    features = chromium_features + app_config.get("features", [])

    desktop_change = False
    if desktop := app_config.get("desktop"):
        desktop_change = write_desktop_override(
            Path(desktop),
            env,
            features,
            app_config.get("switches", []),
            uid,
            gid,
            home,
        )

    local_state_change = False
    if local_state := app_config.get("local_state"):
        local_state_change = patch_chromium_local_state(
            home / local_state,
            app_config.get("local_state_flags", []),
            app_config.get("process_name", app_name),
            uid,
            gid,
        )

    argv_change = False
    if argv_json := app_config.get("argv_json"):
        argv = dict(app_config.get("argv", {}))
        if features:
            argv["enable-features"] = ",".join(features)
        argv_change = merge_electron_argv_json(home / argv_json, argv, uid, gid)

    settings_env_change = False
    if settings_json := app_config.get("settings_json"):
        settings_env_change = merge_settings_json_env(
            home / settings_json,
            app_config.get("settings_env", {}),
            uid,
            gid,
        )

    any_change = (
        desktop_change or local_state_change or argv_change or settings_env_change
    )
    return (any_change, desktop_change)


def refresh_kde_cache(sudo_user: str) -> None:
    """Rebuild KDE's ksycoca cache so .desktop changes propagate to the launcher.
    Without this, kde-systemd-start-app spawns apps with the previously-cached
    Exec line, silently ignoring our updates."""
    if not shutil.which("kbuildsycoca6"):
        return
    try:
        subprocess.run(
            ["runuser", "-u", sudo_user, "--", "kbuildsycoca6", "--noincremental"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Refreshed KDE app cache (kbuildsycoca6)")
    except subprocess.CalledProcessError as e:
        logger.warning(f"kbuildsycoca6 failed: {e.stderr.strip() or 'no output'}")


def main() -> None:
    with APPS_CONFIG_TOML.open("rb") as f:
        config = tomllib.load(f)

    reexec_under_sudo(SCRIPT)

    start_log_tee()

    sudo_user, uid, gid, home = get_invoking_user()

    # Per-app sections are identified by carrying at least one dispatch marker key.
    # Everything else (env, [chromium], future scalars) is filtered out here.
    shared_env = config.get("env", {})
    chromium_features = config.get("chromium", {}).get("features", [])
    dispatch_keys = {"desktop", "settings_json"}
    apps = [
        (name, app_config)
        for name, app_config in config.items()
        if isinstance(app_config, dict) and dispatch_keys & app_config.keys()
    ]
    if not apps:
        logger.info(
            "No app sections in apps_config.toml "
            f"(need one of {sorted(dispatch_keys)}); nothing to do"
        )
        return

    any_change = False
    desktop_change = False
    for app_name, app_config in apps:
        app_any, app_desktop = configure_app(
            app_name, app_config, shared_env, chromium_features, uid, gid, home
        )
        any_change = any_change or app_any
        desktop_change = desktop_change or app_desktop

    if desktop_change:
        refresh_kde_cache(sudo_user)

    logger.info("Done.")
    if any_change:
        logger.info(
            "Restart affected apps to apply (Brave: verify at brave://gpu — "
            "Graphics Feature Status + Video Acceleration Information)."
        )


if __name__ == "__main__":
    main()
