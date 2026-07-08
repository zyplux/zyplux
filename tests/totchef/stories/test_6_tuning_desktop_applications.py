(
    """User stories §6 — Tuning desktop apps. One test per §6 criterion; these cooks edit """
    """real files under `$HOME` (faked by the `home` fixture)."""
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any

    from act_fixtures import Totchef
    from arrange_fixtures import FakeTerminal, RecipeBuilder


def _exec_line(desktop_file: Path) -> str:
    return next(line for line in desktop_file.read_text(encoding="utf-8").splitlines() if line.startswith("Exec="))


# 5.1 Override an app's desktop launcher


def test_6_1_1_desktop_rewrites_exec_line_into_a_user_override(
    recipe: RecipeBuilder, totchef: Totchef, home: Path, tmp_path: Path
) -> None:
    (
        """`[desktop.<app>]` rewrites a system .desktop Exec= line (env prefix, switches, """
        """--enable-features) into ~/.local/share/applications/."""
    )
    source = tmp_path / "brave.desktop"
    source.write_text("[Desktop Entry]\nName=Brave\nExec=/usr/bin/brave %U\n")
    recipe.declares(
        "desktop",
        "brave",
        desktop=str(source),
        env={"LIBVA_DRIVER_NAME": "nvidia"},
        switches=["use-gl=angle"],
        features=["VaapiVideoDecoder"],
    )

    totchef.up().assert_shows("desktop.brave", "applied")

    override = home / ".local/share/applications/brave.desktop"
    line = _exec_line(override)
    assert line.startswith("Exec=env LIBVA_DRIVER_NAME=nvidia /usr/bin/brave")
    assert "--use-gl=angle" in line
    assert "--enable-features=VaapiVideoDecoder" in line
    assert line.split()[-1] == "%U"


def test_6_1_2_desktop_rewrite_is_idempotent_and_deduplicating(
    recipe: RecipeBuilder, totchef: Totchef, home: Path, tmp_path: Path
) -> None:
    (
        """Re-applying doesn't stack duplicate flags; a changed switch value is replaced; """
        """new args go before trailing field codes."""
    )
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


def test_6_1_3_desktop_on_change_refreshes_ksycoca_and_reminds_restart(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, tmp_path: Path
) -> None:
    """On change it refreshes KDE's ksycoca (tolerant of non-KDE) and reminds the operator to restart the app."""
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


def test_6_1_4_desktop_missing_source_reports_install_package_first(
    recipe: RecipeBuilder, totchef: Totchef, tmp_path: Path
) -> None:
    (
        """If the source .desktop doesn't exist, it reports the package must be installed """
        """first rather than failing the run."""
    )
    recipe.declares("desktop", "ghost", desktop=str(tmp_path / "ghost.desktop"), switches=["use-gl=egl"])

    report = totchef.up()

    report.assert_succeeded()
    report.assert_shows("desktop.ghost", "unchanged")
    report.assert_logged("install the package first")


# 5.2 Inject flags into Chromium and Electron apps


def test_6_2_1_1_local_state_merges_into_enabled_labs_experiments(
    recipe: RecipeBuilder, totchef: Totchef, home: Path, read_json: Callable[[Path], Any]
) -> None:
    """`local_state` merges local_state_flags into browser.enabled_labs_experiments of a Chromium Local State JSON."""
    local_state = home / ".config/chromium/Local State"
    local_state.parent.mkdir(parents=True)
    local_state.write_text('{"browser": {"enabled_labs_experiments": ["existing-flag@1"]}}')
    recipe.declares(
        "chromium_flags",
        "chromium",
        local_state=".config/chromium/Local State",
        local_state_flags=["enable-gpu-rasterization@1"],
    )

    totchef.up().assert_shows("chromium_flags.chromium", "applied")

    experiments = read_json(local_state)["browser"]["enabled_labs_experiments"]
    assert "enable-gpu-rasterization@1" in experiments
    assert "existing-flag@1" in experiments


def test_6_2_1_2_argv_json_merges_argv_and_enable_features_tolerating_comments(
    recipe: RecipeBuilder, totchef: Totchef, home: Path, read_json: Callable[[Path], Any]
) -> None:
    (
        """`argv_json` merges an argv table and --enable-features from a features list, """
        """tolerating // comments in the existing file."""
    )
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

    data = read_json(argv_json)
    assert data["locale"] == "en"
    assert data["enable-crash-reporter"] is False
    assert data["enable-features"] == "UseOzonePlatform,WaylandWindowDecorations"


def test_6_2_1_3_chromium_flags_require_exactly_one_target(recipe: RecipeBuilder, totchef: Totchef) -> None:
    """Declaring neither or both of local_state/argv_json is rejected: exactly one target must be set."""
    recipe.declares("chromium_flags", "chromium")  # neither target set

    totchef.lint().assert_rejected("set exactly one of")

    recipe.declares(
        "chromium_flags", "chromium", local_state=".config/chromium/Local State", argv_json=".config/Code/argv.json"
    )  # both targets set

    totchef.lint().assert_rejected("set exactly one of")


def test_6_2_2_chromium_flags_diffed_by_rendered_json_hash(recipe: RecipeBuilder, totchef: Totchef, home: Path) -> None:
    """Diffed by rendered-JSON hash, so it only writes when flags actually change."""
    local_state = home / ".config/chromium/Local State"
    local_state.parent.mkdir(parents=True)
    local_state.write_text('{"browser": {"enabled_labs_experiments": []}}')
    recipe.declares(
        "chromium_flags",
        "chromium",
        local_state=".config/chromium/Local State",
        local_state_flags=["enable-gpu-rasterization@1"],
    )

    totchef.up().assert_shows("chromium_flags.chromium", "applied")
    totchef.up().assert_shows("chromium_flags.chromium", "unchanged")


def test_6_2_3_local_state_skipped_while_browser_running(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, home: Path
) -> None:
    (
        """For Local State it won't write while the browser runs (a pgrep guard skips the """
        """entry), naming the process via process_name if it differs."""
    )
    local_state = home / ".config/BraveSoftware/Brave-Browser/Local State"
    local_state.parent.mkdir(parents=True)
    local_state.write_text('{"browser": {"enabled_labs_experiments": []}}')
    recipe.declares(
        "chromium_flags",
        "brave",
        local_state=".config/BraveSoftware/Brave-Browser/Local State",
        local_state_flags=["x@1"],
        process_name="brave-browser",
    )
    terminal.arrange("pgrep -x brave-browser", exit_code=1)  # `! pgrep` is non-zero ⇒ browser is running ⇒ skip

    report = totchef.up()

    report.assert_shows("chromium_flags.brave", "skipped")
    terminal.expect_ran("pgrep -x brave-browser")


def test_6_2_4_missing_base_file_advises_launch_once_invalid_json_soft_fails(
    recipe: RecipeBuilder, totchef: Totchef, home: Path
) -> None:
    (
        """A missing base file tells the operator to launch the app once and re-run; """
        """invalid JSON is left untouched and soft-fails."""
    )
    broken = home / ".config/electron/argv.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{ not valid json")
    recipe.declares(
        "chromium_flags", "chromium", local_state=".config/chromium/Local State", local_state_flags=["x@1"]
    )  # base file absent
    recipe.declares("chromium_flags", "electron", argv_json=".config/electron/argv.json", features=["UseOzonePlatform"])

    report = totchef.up()

    report.assert_soft_failed()
    report.assert_shows("chromium_flags.chromium", "unchanged")
    report.assert_logged("launch the app once")
    report.assert_logged("invalid JSON")


def test_6_2_5_chromium_flags_on_change_reminds_restart(recipe: RecipeBuilder, totchef: Totchef, home: Path) -> None:
    """On change it reminds the operator to restart the app."""
    argv_json = home / ".config/Code/argv.json"
    argv_json.parent.mkdir(parents=True)
    argv_json.write_text("{}\n")
    recipe.declares("chromium_flags", "code", argv_json=".config/Code/argv.json", features=["UseOzonePlatform"])

    report = totchef.up()

    report.assert_shows("chromium_flags.code", "applied")
    report.assert_logged("restart the app")


def test_6_2_6_a_base_file_that_parses_but_is_not_the_expected_shape_soft_fails_the_same_way(
    recipe: RecipeBuilder, totchef: Totchef, home: Path
) -> None:
    """Syntactically valid JSON that isn't the expected shape soft-fails, never crashes — local_state and argv_json."""
    local_state = home / ".config/chromium/Local State"
    local_state.parent.mkdir(parents=True)
    recipe.declares("chromium_flags", "chromium", local_state=".config/chromium/Local State", local_state_flags=["x@1"])

    local_state.write_text("[1, 2, 3]")
    array_report = totchef.up()
    array_report.assert_soft_failed()
    array_report.assert_logged("invalid JSON")

    local_state.write_text('{"browser": "not-an-object"}')
    bad_browser_report = totchef.up()
    bad_browser_report.assert_soft_failed()
    bad_browser_report.assert_logged("invalid JSON")

    argv_json = home / ".config/Code/argv.json"
    argv_json.parent.mkdir(parents=True)
    recipe.declares("chromium_flags", "code", argv_json=".config/Code/argv.json", features=["UseOzonePlatform"])

    argv_json.write_text("[1, 2, 3]")
    argv_array_report = totchef.up()
    argv_array_report.assert_soft_failed()
    argv_array_report.assert_logged("invalid JSON")


# 5.3 Merge environment settings into a JSON config


def test_6_3_1_settings_merges_settings_env_into_env_preserving_other_keys(
    recipe: RecipeBuilder, totchef: Totchef, home: Path, read_json: Callable[[Path], Any]
) -> None:
    """`[settings.<app>]` merges settings_env into the env object of a JSON file, keeping all other keys intact."""
    settings = home / ".claude/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"theme": "dark", "env": {"EXISTING": "1"}}')
    recipe.declares(
        "settings", "claude", settings_json=".claude/settings.json", settings_env={"DISABLE_TELEMETRY": "1"}
    )

    totchef.up().assert_shows("settings.claude", "applied")

    data = read_json(settings)
    assert data["theme"] == "dark"
    assert data["env"] == {"EXISTING": "1", "DISABLE_TELEMETRY": "1"}


def test_6_3_2_settings_diffed_by_merged_json_hash_invalid_json_soft_fails(
    recipe: RecipeBuilder, totchef: Totchef, home: Path
) -> None:
    """Diffed by merged-JSON hash; invalid JSON is left as-is and soft-fails."""
    settings = home / ".claude/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"env": {}}')
    recipe.declares(
        "settings", "claude", settings_json=".claude/settings.json", settings_env={"DISABLE_TELEMETRY": "1"}
    )

    totchef.up().assert_shows("settings.claude", "applied")
    totchef.up().assert_shows("settings.claude", "unchanged")

    settings.write_text("{ broken json")
    report = totchef.up()

    report.assert_soft_failed()
    report.assert_logged("invalid JSON")


def test_6_3_3_settings_file_that_parses_but_is_not_an_object_soft_fails_the_same_way(
    recipe: RecipeBuilder, totchef: Totchef, home: Path
) -> None:
    """Syntactically valid JSON that isn't an object (or whose `env` isn't) soft-fails, never crashes."""
    settings = home / ".claude/settings.json"
    settings.parent.mkdir(parents=True)
    recipe.declares(
        "settings", "claude", settings_json=".claude/settings.json", settings_env={"DISABLE_TELEMETRY": "1"}
    )

    settings.write_text("[1, 2, 3]")
    array_report = totchef.up()
    array_report.assert_soft_failed()
    array_report.assert_logged("invalid JSON")

    settings.write_text('{"env": "not-an-object"}')
    bad_env_report = totchef.up()
    bad_env_report.assert_soft_failed()
    bad_env_report.assert_logged("invalid JSON")
