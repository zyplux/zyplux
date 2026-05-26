"""User stories §5 — Tuning desktop applications (per-user domains).

One prose-style test per acceptance criterion in `user-stories.md` §5. These cooks
edit files under `$HOME` (redirected to a temp dir by the `home` fixture), so the
reads/writes are real — only the home directory is faked.
"""

import json


def _exec_line(desktop_file) -> str:
    return next(line for line in desktop_file.read_text().splitlines() if line.startswith("Exec="))


# 5.1 Override an app's desktop launcher


def test_5_1_1_desktop_rewrites_exec_line_into_a_user_override(recipe, totchef, home, tmp_path):
    """`[desktop.<app>]` rewrites a system .desktop Exec= line (env prefix, switches,
    --enable-features) into ~/.local/share/applications/."""
    source = tmp_path / "brave.desktop"
    source.write_text("[Desktop Entry]\nName=Brave\nExec=/usr/bin/brave %U\n")
    recipe.declares("desktop", "brave", desktop=str(source), env={"LIBVA_DRIVER_NAME": "nvidia"}, switches=["use-gl=angle"], features=["VaapiVideoDecoder"])

    totchef.up().assert_shows("desktop.brave", "applied")

    override = home / ".local/share/applications/brave.desktop"
    line = _exec_line(override)
    assert line.startswith("Exec=env LIBVA_DRIVER_NAME=nvidia /usr/bin/brave")
    assert "--use-gl=angle" in line
    assert "--enable-features=VaapiVideoDecoder" in line
    assert line.split()[-1] == "%U"


def test_5_1_2_desktop_rewrite_is_idempotent_and_deduplicating(recipe, totchef, home, tmp_path):
    """Re-applying doesn't stack duplicate flags; a changed switch value is replaced;
    new args go before trailing field codes."""
    source = tmp_path / "brave.desktop"
    source.write_text("[Desktop Entry]\nExec=env OLD=1 /usr/bin/brave --use-gl=angle %U\n")
    recipe.declares("desktop", "brave", desktop=str(source), switches=["use-gl=egl"], features=["VaapiVideoDecoder"])

    totchef.up().assert_shows("desktop.brave", "applied")

    line = _exec_line(home / ".local/share/applications/brave.desktop")
    assert line.count("--use-gl=") == 1
    assert "--use-gl=egl" in line
    assert "--use-gl=angle" not in line
    assert line.split()[-1] == "%U"

    totchef.up().assert_shows("desktop.brave", "unchanged")


def test_5_1_3_desktop_on_change_refreshes_ksycoca_and_reminds_restart(recipe, terminal, totchef, tmp_path):
    """On change it refreshes KDE's ksycoca (tolerant of non-KDE) and reminds the
    operator to restart the app."""
    source = tmp_path / "brave.desktop"
    source.write_text("[Desktop Entry]\nExec=/usr/bin/brave %U\n")
    recipe.declares("desktop", "brave", desktop=str(source), switches=["use-gl=egl"])

    report = totchef.up()

    report.assert_shows("desktop.brave", "applied")
    report.assert_logged("Restart the app")
    terminal.expect_ran("kbuildsycoca6")

    terminal.reset()
    totchef.up().assert_shows("desktop.brave", "unchanged")
    terminal.expect_not_ran("kbuildsycoca6")


def test_5_1_4_desktop_missing_source_reports_install_package_first(recipe, totchef, tmp_path):
    """If the source .desktop doesn't exist, it reports the package must be installed
    first rather than failing the run."""
    recipe.declares("desktop", "ghost", desktop=str(tmp_path / "ghost.desktop"), switches=["use-gl=egl"])

    report = totchef.up()

    report.assert_succeeded()
    report.assert_shows("desktop.ghost", "unchanged")
    report.assert_logged("install the package first")


# 5.2 Inject flags into Chromium and Electron apps


def test_5_2_1_1_local_state_merges_into_enabled_labs_experiments(recipe, totchef, home):
    """`local_state` merges local_state_flags into
    browser.enabled_labs_experiments of a Chromium Local State JSON."""
    local_state = home / ".config/chromium/Local State"
    local_state.parent.mkdir(parents=True)
    local_state.write_text(json.dumps({"browser": {"enabled_labs_experiments": ["existing-flag@1"]}}))
    recipe.declares("chromium_flags", "chromium", local_state=".config/chromium/Local State", local_state_flags=["enable-gpu-rasterization@1"])

    totchef.up().assert_shows("chromium_flags.chromium", "applied")

    experiments = json.loads(local_state.read_text())["browser"]["enabled_labs_experiments"]
    assert "enable-gpu-rasterization@1" in experiments
    assert "existing-flag@1" in experiments


def test_5_2_1_2_argv_json_merges_argv_and_enable_features_tolerating_comments(recipe, totchef, home):
    """`argv_json` merges an argv table and --enable-features from a features list,
    tolerating // comments in the existing file."""
    argv_json = home / ".config/Code/argv.json"
    argv_json.parent.mkdir(parents=True)
    argv_json.write_text('// Code runtime args\n{\n  "locale": "en"\n}\n')
    recipe.declares(
        "chromium_flags",
        "code",
        argv_json=".config/Code/argv.json",
        argv={"enable-crash-reporter": False},
        features=["UseOzonePlatform", "WaylandWindowDecorations"],
    )

    totchef.up().assert_shows("chromium_flags.code", "applied")

    data = json.loads(argv_json.read_text())
    assert data["locale"] == "en"
    assert data["enable-crash-reporter"] is False
    assert data["enable-features"] == "UseOzonePlatform,WaylandWindowDecorations"


def test_5_2_2_chromium_flags_diffed_by_rendered_json_hash(recipe, totchef, home):
    """Diffed by rendered-JSON hash, so it only writes when flags actually change."""
    local_state = home / ".config/chromium/Local State"
    local_state.parent.mkdir(parents=True)
    local_state.write_text(json.dumps({"browser": {"enabled_labs_experiments": []}}))
    recipe.declares("chromium_flags", "chromium", local_state=".config/chromium/Local State", local_state_flags=["enable-gpu-rasterization@1"])

    totchef.up().assert_shows("chromium_flags.chromium", "applied")
    totchef.up().assert_shows("chromium_flags.chromium", "unchanged")


def test_5_2_3_local_state_skipped_while_browser_running(recipe, terminal, totchef, home):
    """For Local State it won't write while the browser runs (a pgrep guard skips
    the entry), naming the process via process_name if it differs."""
    local_state = home / ".config/BraveSoftware/Brave-Browser/Local State"
    local_state.parent.mkdir(parents=True)
    local_state.write_text(json.dumps({"browser": {"enabled_labs_experiments": []}}))
    recipe.declares(
        "chromium_flags", "brave", local_state=".config/BraveSoftware/Brave-Browser/Local State", local_state_flags=["x@1"], process_name="brave-browser"
    )
    terminal.arrange("pgrep -x brave-browser", exit_code=1)  # `! pgrep` is non-zero ⇒ browser is running ⇒ skip

    report = totchef.up()

    report.assert_shows("chromium_flags.brave", "skipped")
    terminal.expect_ran("pgrep -x brave-browser")


def test_5_2_4_missing_base_file_advises_launch_once_invalid_json_soft_fails(recipe, totchef, home):
    """A missing base file tells the operator to launch the app once and re-run;
    invalid JSON is left untouched and soft-fails."""
    broken = home / ".config/electron/argv.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{ not valid json")
    recipe.declares("chromium_flags", "chromium", local_state=".config/chromium/Local State", local_state_flags=["x@1"])  # base file absent
    recipe.declares("chromium_flags", "electron", argv_json=".config/electron/argv.json", features=["UseOzonePlatform"])

    report = totchef.up()

    report.assert_soft_failed()
    report.assert_shows("chromium_flags.chromium", "unchanged")
    report.assert_logged("launch the app once")
    report.assert_logged("invalid JSON")


def test_5_2_5_chromium_flags_on_change_reminds_restart(recipe, totchef, home):
    """On change it reminds the operator to restart the app."""
    argv_json = home / ".config/Code/argv.json"
    argv_json.parent.mkdir(parents=True)
    argv_json.write_text("{}\n")
    recipe.declares("chromium_flags", "code", argv_json=".config/Code/argv.json", features=["UseOzonePlatform"])

    report = totchef.up()

    report.assert_shows("chromium_flags.code", "applied")
    report.assert_logged("restart the app")


# 5.3 Merge environment settings into a JSON config


def test_5_3_1_settings_merges_settings_env_into_env_preserving_other_keys(recipe, totchef, home):
    """`[settings.<app>]` merges settings_env into the env object of a JSON file,
    keeping all other keys intact."""
    settings = home / ".claude/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"theme": "dark", "env": {"EXISTING": "1"}}))
    recipe.declares("settings", "claude", settings_json=".claude/settings.json", settings_env={"DISABLE_TELEMETRY": "1"})

    totchef.up().assert_shows("settings.claude", "applied")

    data = json.loads(settings.read_text())
    assert data["theme"] == "dark"
    assert data["env"] == {"EXISTING": "1", "DISABLE_TELEMETRY": "1"}


def test_5_3_2_settings_diffed_by_merged_json_hash_invalid_json_soft_fails(recipe, totchef, home):
    """Diffed by merged-JSON hash; invalid JSON is left as-is and soft-fails."""
    settings = home / ".claude/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"env": {}}))
    recipe.declares("settings", "claude", settings_json=".claude/settings.json", settings_env={"DISABLE_TELEMETRY": "1"})

    totchef.up().assert_shows("settings.claude", "applied")
    totchef.up().assert_shows("settings.claude", "unchanged")

    settings.write_text("{ broken json")
    report = totchef.up()

    report.assert_soft_failed()
    report.assert_logged("invalid JSON")
