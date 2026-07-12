(
    """User stories §1 — Running totchef. One test per §1 criterion: apply/plan drive the """
    """chef, the CLI stories run the real command under `tmp_path`."""
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest
    from act_fixtures import Cli, Totchef
    from arrange_fixtures import FakeTerminal, RecipeBuilder

# 1.1 Apply a recipe to converge the system


def test_1_1_1_up_resolves_validates_escalates_previews_then_executes(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, cli: Cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        """`totchef up` resolves the recipe, validates it, escalates to root, then previews """
        """and executes — creating or updating every resource that differs."""
    )
    target = totchef.workdir / "drop.conf"
    recipe.declares("file", "drop", path=str(target), content="X=1\n")
    recipe.declares("bash", "tweak", current_state="probe", desired_state="ok", apply="make-it-ok")
    terminal.arrange("probe", "drift")  # current state differs from desired

    report = totchef.up()

    report.assert_succeeded()
    report.assert_shows("file.drop", "applied")  # created
    report.assert_shows("bash.tweak", "applied")  # updated
    assert target.read_text() == "X=1\n"

    # validation comes first: an invalid recipe is rejected before the sudo re-exec ever happens
    invalid = totchef.workdir / "invalid.toml"
    invalid.write_text("[nosuchsection]\nx = 1\n")
    escalated: dict[str, str] = {}

    def capture_exec(target: str, _argv: list[str]) -> None:
        escalated["target"] = target
        raise SystemExit(0)  # sudo would replace the process here

    monkeypatch.setattr("os.geteuid", lambda: 1000)  # not root yet
    monkeypatch.setattr("os.execvp", capture_exec)
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)

    rejected = cli.run("up", "--recipe", str(invalid))

    assert not escalated  # rejected before any sudo prompt …
    rejected.assert_failed()
    rejected.assert_prints("no cook registered")  # … with the schema error on the real stderr


def test_1_1_2_up_is_idempotent_rerun_reports_nothing_changed(
    recipe: RecipeBuilder, totchef: Totchef, tmp_path: Path
) -> None:
    (
        """Re-running when nothing has drifted reports "nothing changed" and makes no """
        """modifications; the second run only touches what genuinely differs."""
    )
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    totchef.up().assert_shows("file.f", "applied")

    second = totchef.up()
    second.assert_shows("file.f", "unchanged")
    assert "nothing changed" in second.report


def test_1_1_3_exit_code_communicates_outcome(
    scenario: Callable[[], RecipeBuilder],
    chef: Callable[[RecipeBuilder], Totchef],
    terminal: FakeTerminal,
    tmp_path: Path,
) -> None:
    """Exit code: 0 success, 75 soft failure (recoverable), 1 hard failure (aborted)."""
    chef(scenario().declares("file", "ok", path=str(tmp_path / "ok"), content="X\n")).up().assert_succeeded()

    soft = scenario().declares("file", "g", path=str(tmp_path / "g"), content="X\n", post_hook="refresh-fails")
    terminal.arrange("refresh-fails", exit_code=1)
    chef(soft).up().assert_soft_failed()

    hard = scenario().declares("bash", "b", apply="boom")
    terminal.arrange("boom", exit_code=1)
    chef(hard).up().assert_hard_failed()


def test_1_1_4_invalid_recipe_rejects_the_run_before_any_apply(
    recipe: RecipeBuilder, totchef: Totchef, tmp_path: Path
) -> None:
    (
        """Every run lints the recipe first: one invalid entry rejects the whole `up` before """
        """any cook applies, so even the valid entries' targets stay untouched."""
    )
    valid_target = tmp_path / "ok.conf"
    recipe.declares("file", "ok", path=str(valid_target), content="X=1\n")
    recipe.declares("file", "broken", path=str(tmp_path / "broken"), content="a", typo=1)

    rejected = totchef.up()

    rejected.assert_rejected("typo")
    assert not valid_target.exists()  # validation gated the run; nothing applied


# 1.2 Preview changes without touching the system


def test_1_2_1_plan_dry_run_prints_table_makes_no_changes(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, tmp_path: Path
) -> None:
    (
        """`totchef plan` probes state and prints the plan table (would install / upgrade / """
        """apply, up-to-date, ok) but makes no changes."""
    )
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")
    recipe.declares("bash", "step", current_state="probe", desired_state="ok", apply="make-it-ok")
    terminal.arrange("probe", "drift")

    plan = totchef.plan()

    plan.assert_shows("file.f", "would apply")
    plan.assert_shows("bash.step", "would apply")
    terminal.expect_not_ran("make-it-ok")
    assert not (tmp_path / "f").exists()


def test_1_2_2_plan_requires_no_root(
    terminal: FakeTerminal,
    totchef: Totchef,
    cli: Cli,
    git_needs_install: str,
    escalation_probe: Callable[[], list[tuple[str, list[str]]]],
) -> None:
    """A dry run never escalates privileges."""
    totchef.recipe.declares("apt_pkg", packages=["git"])  # a root-scoped cook, planned without root
    terminal.arrange("apt-cache policy git", git_needs_install)

    totchef.plan().assert_shows("apt_pkg.git", "would install")
    terminal.expect_not_ran("nala")  # no privileged transaction

    # the real gate: a dry run from a non-root euid never re-execs under sudo
    escalations = escalation_probe()
    recipe_path = totchef.workdir / "recipe.toml"
    recipe_path.write_text('[apt_pkg]\npackages = ["git"]\n')

    cli.run("plan", "--recipe", str(recipe_path)).assert_succeeded()

    assert escalations == []  # plan ran to completion without ever escalating


def test_1_2_3_plan_shows_all_resources_including_unchanged(
    recipe: RecipeBuilder, totchef: Totchef, tmp_path: Path
) -> None:
    """The plan shows every resource, not just the diff, so the full intended end state is visible."""
    settled = tmp_path / "settled"
    settled.write_text("X\n")  # already matches the desired content
    settled.chmod(0o644)  # …and mode
    recipe.declares("file", "settled", path=str(settled), content="X\n")
    recipe.declares("bash", "step", apply="do-it")

    plan = totchef.plan()

    plan.assert_shows("file.settled", "ok")  # unchanged, but still shown
    plan.assert_shows("bash.step", "would apply")
    assert "file.settled" in plan.report
    assert "bash.step" in plan.report


def test_1_2_4_up_prints_plan_first_from_silent_probe(recipe: RecipeBuilder, totchef: Totchef, tmp_path: Path) -> None:
    """During a real `up`, the same plan is printed first from a silent probe pass — before the converging run."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    report = totchef.up()
    shown = report.terminal_report

    assert shown.index("Plan") < shown.index("Report")  # the probe's plan table is printed before the converging report
    assert "would apply" in shown  # the plan previews the pending change (probed from pre-run state) …
    assert "applied" in shown  # … then the report shows the converging run made it


# 1.3 Find out which recipe will be used


def test_1_3_1_where_prints_resolved_recipe_path(cli: Cli, tmp_path: Path) -> None:
    """`totchef where` prints the resolved recipe path and exits."""
    recipe_path = tmp_path / "recipe.toml"
    recipe_path.write_text("")

    cli.run("where", "--recipe", str(recipe_path)).assert_prints(str(recipe_path))


def test_1_3_2_recipe_discovery_follows_fixed_precedence(
    cli: Cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        """Precedence: --recipe/-r (file or dir), then a recognized recipe name walking up """
        """from the cwd, then a recipe pinned by `totchef init`."""
    )
    explicit = tmp_path / "explicit.toml"
    explicit.write_text("")
    cli.run("where", "--recipe", str(explicit)).assert_prints(str(explicit))  # an explicit flag wins

    project = tmp_path / "project"
    (project / "sub").mkdir(parents=True)
    (project / "totchef_recipe.toml").write_text("")
    monkeypatch.chdir(project / "sub")
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)
    # then a recognized name, walking up from cwd
    cli.run("where").assert_prints(str(project / "totchef_recipe.toml"))

    pinned = tmp_path / "pinned" / "totchef.toml"
    pinned.parent.mkdir(parents=True)
    pinned.write_text("")
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()
    monkeypatch.chdir(nowhere)
    cli.run("init", str(pinned)).assert_succeeded()
    cli.run("where").assert_prints(
        str(pinned)
    )  # then the recipe pinned by `totchef init`, when nothing nearer is found


def test_1_3_3_no_recipe_found_lists_searched_locations(
    cli: Cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When no recipe is found, the error lists every location searched."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)

    missing = cli.run("where")

    missing.assert_failed()
    missing.assert_prints("Looked in")
    missing.assert_prints("recipe.toml")


def test_1_3_4_recipe_flag_accepts_a_directory(cli: Cli, tmp_path: Path) -> None:
    """`--recipe DIR` resolves to a recognized recipe filename inside that directory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "totchef_recipe.toml").write_text("")

    cli.run("where", "--recipe", str(repo)).assert_prints(str(repo / "totchef_recipe.toml"))


def test_1_3_5_init_pins_a_default_recipe(
    cli: Cli, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`totchef init PATH` saves the recipe location so a later run with nothing nearer resolves to it."""
    recipe_path = tmp_path / "dots" / "totchef_recipe.toml"
    recipe_path.parent.mkdir(parents=True)
    recipe_path.write_text("")

    cli.run("init", str(recipe_path)).assert_succeeded()

    assert str(recipe_path) in (home / ".config/totchef/config.toml").read_text()  # pinned in the user config

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)
    cli.run("where").assert_prints(str(recipe_path))  # the pinned recipe is the fallback


def test_1_3_6_init_offers_the_discovered_recipe(
    cli: Cli, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        """Run with no path, `totchef init` offers the recipe discovered in the current """
        """directory and pins it on confirmation."""
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    recipe_path = repo / "totchef.toml"
    recipe_path.write_text("")
    monkeypatch.chdir(repo)
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)

    confirmed = cli.run("init", stdin="y\n")  # answer the prompt

    confirmed.assert_succeeded()
    confirmed.assert_prints(str(recipe_path))  # the prompt named the discovered recipe
    assert str(recipe_path) in (home / ".config/totchef/config.toml").read_text()  # and it was pinned


def test_1_3_7_init_pins_a_symlink_as_given(
    cli: Cli, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        """`totchef init PATH` pins a symlinked PATH as given rather than dereferencing it, """
        """so repointing the symlink later moves the pin without rerunning init."""
    )
    real = tmp_path / "real" / "totchef_recipe.toml"
    real.parent.mkdir(parents=True)
    real.write_text("")
    link = tmp_path / "pinned.toml"
    link.symlink_to(real)

    cli.run("init", str(link)).assert_succeeded()

    assert str(link) in (home / ".config/totchef/config.toml").read_text()  # the symlink path is pinned, not its target

    moved = tmp_path / "moved" / "totchef_recipe.toml"
    moved.parent.mkdir(parents=True)
    moved.write_text("")
    link.unlink()
    link.symlink_to(moved)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)
    cli.run("where").assert_prints(str(moved))  # repointing the symlink moved the pin without touching init


def test_1_3_8_init_errors_when_no_recipe_is_found_and_none_pinned(
    cli: Cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no path, nothing discoverable, and nothing pinned yet, `init` rejects instead of pinning nothing."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)

    missing = cli.run("init")

    missing.assert_failed()
    missing.assert_prints("no recipe found here to pin")


# 1.4 Discover available cooks


def test_1_4_1_cooks_lists_section_scope_and_origin(cli: Cli) -> None:
    (
        """`totchef --list-cooks` prints section, scope (root/user), and origin (built-in / """
        """plugin:<dist> / local:<path>) for every resolvable cook."""
    )
    cli.run("--list-cooks").assert_output("""
        [18]{section,scope,origin}:
          apt_pkg,root,built-in
          apt_repo,root,built-in
          bash,user,built-in
          bun,user,built-in
          cargo,user,built-in
          chromium_flags,user,built-in
          conf,user,built-in
          desktop,user,built-in
          file,user,built-in
          local_bin,user,built-in
          local_bin_dir,user,built-in
          settings,user,built-in
          skills,user,built-in
          snap,root,built-in
          url,user,built-in
          usr_local_bin,root,built-in
          usr_local_sbin,root,built-in
          uv,user,built-in
    """)


def test_1_4_2_cooks_reflects_live_registry(cli: Cli, home: Path) -> None:
    """An installed plugin or a dropped-in local cook shows up immediately."""
    cooks_dir = home / ".config/totchef/cooks"
    cooks_dir.mkdir(parents=True)
    (cooks_dir / "widget_cook.py").write_text(
        "from totchef.cook_base import StateCook, StateChangeOutcome, EntrySpec\n"
        "class WidgetEntry(EntrySpec):\n"
        "    value: str = ''\n"
        "class WidgetCook(StateCook):\n"
        "    entry_model = WidgetEntry\n"
        "    def get_current_state(self): return {}\n"
        "    def get_desired_state(self): return {}\n"
        "    def apply_resource(self, name): return StateChangeOutcome(changed=False)\n"
    )

    cli.run("--list-cooks").assert_lists("widget", origin="local")


# 1.5 Check the version


def test_1_5_version_reports_installed_version(cli: Cli) -> None:
    """`totchef --version` reports the installed version."""
    version = cli.run("--version")

    version.assert_succeeded()
    version.assert_prints("totchef ")
    assert "." in version.output
    assert any(char.isdigit() for char in version.output)
