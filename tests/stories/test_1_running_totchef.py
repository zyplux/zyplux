"""User stories §1 — Running totchef. One test per §1 criterion: apply/plan drive the chef, the CLI stories run the real command under `tmp_path`."""

GIT_NEEDS_INSTALL = "git:\n  Installed: (none)\n  Candidate: 1:2.40\n  Version table:\n     1:2.40 500\n        500 http://archive noble/main amd64 Packages\n"


# 1.1 Apply a recipe to converge the system


def test_1_1_1_up_resolves_escalates_validates_previews_then_executes(recipe, terminal, totchef, tmp_path, cli, monkeypatch):
    """`totchef up` resolves the recipe, escalates to root, then validates, previews, and executes — creating or updating every resource that differs."""
    target = tmp_path / "drop.conf"
    recipe.declares("file", "drop", path=str(target), content="X=1\n")
    recipe.declares("bash", "tweak", current_state="probe", desired_state="ok", apply="make-it-ok")
    terminal.arrange("probe", "drift")  # current state differs from desired

    report = totchef.up()

    report.assert_succeeded()
    report.assert_shows("file.drop", "applied")  # created
    report.assert_shows("bash.tweak", "applied")  # updated
    assert target.read_text() == "X=1\n"

    # escalation comes first: even an invalid recipe re-execs under sudo *before* validation surfaces
    invalid = tmp_path / "invalid.toml"
    invalid.write_text("[nosuchsection]\nx = 1\n")
    escalated: dict = {}

    def capture_exec(target: str, argv: list[str]) -> None:
        escalated["target"] = target
        raise SystemExit(0)  # sudo replaces the process — control never returns to validate the recipe

    monkeypatch.setattr("os.geteuid", lambda: 1000)  # not root yet
    monkeypatch.setattr("os.execvp", capture_exec)
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)

    rejected = cli.run("up", "--recipe", str(invalid))

    assert escalated["target"] == "sudo"  # escalated …
    assert "no cook registered" not in rejected.output  # … before the recipe was validated, so the schema error never surfaced


def test_1_1_2_up_is_idempotent_rerun_reports_nothing_changed(recipe, totchef, tmp_path):
    """Re-running when nothing has drifted reports "nothing changed" and makes no modifications; the second run only touches what genuinely differs."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    totchef.up().assert_shows("file.f", "applied")

    second = totchef.up()
    second.assert_shows("file.f", "unchanged")
    assert "nothing changed" in second.report


def test_1_1_3_exit_code_communicates_outcome(scenario, chef, terminal, tmp_path):
    """Exit code: 0 success, 75 soft failure (recoverable), 1 hard failure (aborted)."""
    chef(scenario().declares("file", "ok", path=str(tmp_path / "ok"), content="X\n")).up().assert_succeeded()

    soft = scenario().declares("file", "g", path=str(tmp_path / "g"), content="X\n", post_hook="refresh-fails")
    terminal.arrange("refresh-fails", exit_code=1)
    chef(soft).up().assert_soft_failed()

    hard = scenario().declares("bash", "b", apply="boom")
    terminal.arrange("boom", exit_code=1)
    chef(hard).up().assert_hard_failed()


# 1.2 Preview changes without touching the system


def test_1_2_1_plan_dry_run_prints_table_makes_no_changes(recipe, terminal, totchef, tmp_path):
    """`totchef plan` probes state and prints the plan table (would install / upgrade / apply, up-to-date, ok) but makes no changes."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")
    recipe.declares("bash", "step", current_state="probe", desired_state="ok", apply="make-it-ok")
    terminal.arrange("probe", "drift")

    plan = totchef.plan()

    plan.assert_shows("file.f", "would apply")
    plan.assert_shows("bash.step", "would apply")
    terminal.expect_not_ran("make-it-ok")
    assert not (tmp_path / "f").exists()


def test_1_2_2_plan_requires_no_root(recipe, terminal, totchef, cli, monkeypatch, tmp_path):
    """A dry run never escalates privileges."""
    recipe.declares("apt_pkg", packages=["git"])  # a root-scoped cook, planned without root
    terminal.arrange("apt-cache policy git", GIT_NEEDS_INSTALL)

    totchef.plan().assert_shows("apt_pkg.git", "would install")
    terminal.expect_not_ran("nala")  # no privileged transaction

    # the real gate: a dry run from a non-root euid never re-execs under sudo
    escalations: list = []
    monkeypatch.setattr("os.geteuid", lambda: 1000)  # not root — so any escalation would call execvp
    monkeypatch.setattr("os.execvp", lambda *argv: escalations.append(argv))
    monkeypatch.setattr("totchef.cli.run_recipe", lambda config, dry_run: {})  # don't fork real cooks in-process
    monkeypatch.setattr("totchef.cli.start_logging", lambda echo_to_terminal=True: tmp_path / "log")
    monkeypatch.setattr("totchef.cli.drain_logs", lambda: None)
    recipe_path = tmp_path / "recipe.toml"
    recipe_path.write_text('[apt_pkg]\npackages = ["git"]\n')

    cli.run("plan", "--recipe", str(recipe_path)).assert_succeeded()

    assert escalations == []  # plan ran to completion without ever escalating


def test_1_2_3_plan_shows_all_resources_including_unchanged(recipe, totchef, tmp_path):
    """The plan shows every resource, not just the diff, so the full intended end state is visible."""
    settled = tmp_path / "settled"
    settled.write_text("X\n")  # already matches the desired content
    recipe.declares("file", "settled", path=str(settled), content="X\n")
    recipe.declares("bash", "step", apply="do-it")

    plan = totchef.plan()

    plan.assert_shows("file.settled", "ok")  # unchanged, but still shown
    plan.assert_shows("bash.step", "would apply")
    assert "file.settled" in plan.report and "bash.step" in plan.report


def test_1_2_4_up_prints_plan_first_from_silent_probe(recipe, totchef, tmp_path):
    """During a real `up`, the same plan is printed first from a silent probe pass — before the converging run."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    report = totchef.up()
    shown = report.terminal_report

    assert shown.index("Plan") < shown.index("Report")  # the probe's plan table is printed before the converging report
    assert "would apply" in shown  # the plan previews the pending change (probed from pre-run state) …
    assert "applied" in shown  # … then the report shows the converging run made it


# 1.3 Validate a recipe without running it


def test_1_3_1_lint_validates_and_prints_path_valid(cli, tmp_path):
    """`totchef lint` validates against every cook's schema and the graph, then prints `<path>: valid` or exits with a precise error."""
    good = tmp_path / "recipe.toml"
    good.write_text('[bash.step]\napply = "true"\n')

    cli.run("lint", "--recipe", str(good)).assert_prints(": valid")

    bad = tmp_path / "bad.toml"
    bad.write_text("[nosuchsection]\nx = 1\n")
    cli.run("lint", "--recipe", str(bad)).assert_failed()


def test_1_3_2_lint_catches_schema_and_graph_errors(scenario, chef):
    """Catches: unregistered section, unknown key, missing-node dependency, cycle, self-dependency, and `needs_root` on a subtable header."""
    chef(scenario().declares("nosuch", packages=[])).lint().assert_rejected()  # unregistered section
    chef(scenario().declares("file", "f", path="/x", content="a", typo=1)).lint().assert_rejected()  # unknown key
    chef(scenario().declares("bash", "a", apply="x", depends_on=["ghost"])).lint().assert_rejected()  # missing node
    chef(scenario().declares("bash", "a", apply="x", depends_on=["bash.a"])).lint().assert_rejected()  # self-dependency

    cyclic = scenario()
    cyclic.declares("bash", "a", apply="x", depends_on=["bash.b"])
    cyclic.declares("bash", "b", apply="y", depends_on=["bash.a"])
    chef(cyclic).lint().assert_rejected()  # cycle

    header = scenario()
    header.declares("bash", needs_root=True)
    header.declares("bash", "s", apply="x")
    chef(header).lint().assert_rejected("needs_root")  # needs_root on a subtable header


def test_1_3_3_lint_needs_no_root_and_changes_nothing(recipe, terminal, totchef, tmp_path):
    """Linting needs no root and changes nothing."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    totchef.lint().assert_valid()  # returns cleanly

    assert not (tmp_path / "f").exists()
    assert terminal.commands == []  # no shell ran at all


# 1.4 Find out which recipe will be used


def test_1_4_1_where_prints_resolved_recipe_path(cli, tmp_path):
    """`totchef where` prints the resolved recipe path and exits."""
    recipe_path = tmp_path / "recipe.toml"
    recipe_path.write_text("")

    cli.run("where", "--recipe", str(recipe_path)).assert_prints(str(recipe_path))


def test_1_4_2_recipe_discovery_follows_fixed_precedence(cli, tmp_path, monkeypatch):
    """Precedence: --recipe/-r, $TOTCHEF_RECIPE, walk up for recipe.toml, ~/.config/totchef/recipe.toml, /etc/totchef/recipe.toml."""
    explicit = tmp_path / "explicit.toml"
    explicit.write_text("")
    cli.run("where", "--recipe", str(explicit)).assert_prints(str(explicit))  # an explicit flag wins

    env_recipe = tmp_path / "env.toml"
    env_recipe.write_text("")
    monkeypatch.setenv("TOTCHEF_RECIPE", str(env_recipe))
    cli.run("where").assert_prints(str(env_recipe))  # then $TOTCHEF_RECIPE
    monkeypatch.delenv("TOTCHEF_RECIPE")

    project = tmp_path / "project"
    (project / "sub").mkdir(parents=True)
    (project / "recipe.toml").write_text("")
    monkeypatch.chdir(project / "sub")
    cli.run("where").assert_prints(str(project / "recipe.toml"))  # then walk up from cwd


def test_1_4_3_no_recipe_found_lists_searched_locations(cli, tmp_path, monkeypatch):
    """When no recipe is found, the error lists every location searched."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)

    missing = cli.run("where")

    missing.assert_failed()
    missing.assert_prints("Looked in")
    missing.assert_prints("recipe.toml")


# 1.5 Discover available cooks


def test_1_5_1_cooks_lists_section_scope_and_origin(cli):
    """`totchef --list-cooks` prints section, scope (root/user), and origin (built-in / plugin:<dist> / local:<path>) for every resolvable cook."""
    cli.run("--list-cooks").assert_output("""
        [12]{section,scope,origin}:
          apt_pkg,root,built-in
          apt_repo,root,built-in
          bash,user,built-in
          bun,user,built-in
          cargo,user,built-in
          chromium_flags,user,built-in
          desktop,user,built-in
          file,user,built-in
          settings,user,built-in
          snap,root,built-in
          url,user,built-in
          uv,user,built-in
    """)


def test_1_5_2_cooks_reflects_live_registry(cli, home):
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


# 1.6 Check the version


def test_1_6_version_reports_installed_version(cli):
    """`totchef --version` reports the installed version."""
    version = cli.run("--version")

    version.assert_succeeded()
    version.assert_prints("totchef ")
    assert "." in version.output and any(char.isdigit() for char in version.output)
