"""User stories §1 — Running totchef.

One prose-style test per acceptance criterion in `user-stories.md` §1. The apply/plan
stories drive the chef in-process; the CLI-plumbing stories (lint output, `where`,
`cooks`, `--version`, recipe discovery) call the real `cli`/`recipe`/`registry`
functions at their boundary, with stdout captured and the filesystem under `tmp_path`.
"""

import typer
import pytest

from framework import RecipeBuilder, RecipeRejected, Totchef
from totchef import __version__, cli
from totchef.recipe import RECIPE_ENV, find_recipe
from totchef.registry import config_cooks_dir, cook_registry

GIT_NEEDS_INSTALL = "git:\n  Installed: (none)\n  Candidate: 1:2.40\n  Version table:\n     1:2.40 500\n        500 http://archive noble/main amd64 Packages\n"


# 1.1 Apply a recipe to converge the system


def test_1_1_1_up_reads_validates_escalates_previews_then_executes(recipe, terminal, totchef, tmp_path):
    """`totchef up` reads the recipe, validates it, escalates to root, previews
    the plan, then executes — creating or updating every resource that differs."""
    target = tmp_path / "drop.conf"
    recipe.declares("file", "drop", path=str(target), content="X=1\n")
    recipe.declares("bash", "tweak", current_state="probe", desired_state="ok", apply="make-it-ok")
    terminal.arrange("probe", "drift")  # current state differs from desired

    report = totchef.up()

    report.assert_succeeded()
    report.assert_shows("file.drop", "applied")  # created
    report.assert_shows("bash.tweak", "applied")  # updated
    assert target.read_text() == "X=1\n"


def test_1_1_2_up_is_idempotent_rerun_reports_nothing_changed(recipe, totchef, tmp_path):
    """Re-running when nothing has drifted reports "nothing changed" and makes no
    modifications; the second run only touches what genuinely differs."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    totchef.up().assert_shows("file.f", "applied")

    second = totchef.up()
    second.assert_shows("file.f", "unchanged")
    assert "nothing changed" in second.report


def test_1_1_3_exit_code_communicates_outcome(recipe, terminal, totchef, tmp_path):
    """Exit code: 0 success, 75 soft failure (recoverable), 1 hard failure (aborted)."""
    recipe.declares("file", "ok", path=str(tmp_path / "ok"), content="X\n")
    assert totchef.up().exit_code == 0

    soft = Totchef(RecipeBuilder().declares("file", "g", path=str(tmp_path / "g"), content="X\n", post_hook="refresh-fails"), terminal)
    terminal.arrange("refresh-fails", exit_code=1)
    assert soft.up().exit_code == 75

    hard = Totchef(RecipeBuilder().declares("bash", "b", apply="boom"), terminal)
    terminal.arrange("boom", exit_code=1)
    assert hard.up().exit_code == 1


# 1.2 Preview changes without touching the system


def test_1_2_1_plan_dry_run_prints_table_makes_no_changes(recipe, terminal, totchef, tmp_path):
    """`totchef plan` probes state and prints the plan table (would install /
    upgrade / apply, up-to-date, ok) but makes no changes."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")
    recipe.declares("bash", "step", current_state="probe", desired_state="ok", apply="make-it-ok")
    terminal.arrange("probe", "drift")

    plan = totchef.plan()

    plan.assert_shows("file.f", "would apply")
    plan.assert_shows("bash.step", "would apply")
    terminal.expect_not_ran("make-it-ok")
    assert not (tmp_path / "f").exists()


def test_1_2_2_plan_requires_no_root(recipe, terminal, totchef):
    """A dry run never escalates privileges."""
    recipe.declares("apt_pkg", packages=["git"])  # a root-scoped cook, planned without root
    terminal.arrange("apt-cache policy git", GIT_NEEDS_INSTALL)

    totchef.plan().assert_shows("apt_pkg.git", "would install")
    terminal.expect_not_ran("nala")  # no privileged transaction


def test_1_2_3_plan_shows_all_resources_including_unchanged(recipe, totchef, tmp_path):
    """The plan shows every resource, not just the diff, so the full intended end
    state is visible."""
    settled = tmp_path / "settled"
    settled.write_text("X\n")  # already matches the desired content
    recipe.declares("file", "settled", path=str(settled), content="X\n")
    recipe.declares("bash", "step", apply="do-it")

    plan = totchef.plan()

    plan.assert_shows("file.settled", "ok")  # unchanged, but still shown
    plan.assert_shows("bash.step", "would apply")
    assert "file.settled" in plan.report and "bash.step" in plan.report


def test_1_2_4_up_prints_plan_first_from_silent_probe(recipe, totchef, tmp_path):
    """During a real `up`, the same plan is printed first from a silent probe pass."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    preview = totchef.plan()  # the silent probe pass an `up` runs first
    preview.assert_shows("file.f", "would apply")

    totchef.up().assert_shows("file.f", "applied")  # then it executes exactly that


# 1.3 Validate a recipe without running it


def test_1_3_1_lint_validates_and_prints_path_valid(tmp_path, capsys):
    """`totchef lint` validates against every cook's schema and the graph, then
    prints `<path>: valid` or exits with a precise error."""
    good = tmp_path / "recipe.toml"
    good.write_text('[bash.step]\napply = "true"\n')

    cli.lint(good)

    assert ": valid" in capsys.readouterr().out

    bad = tmp_path / "bad.toml"
    bad.write_text("[nosuchsection]\nx = 1\n")
    with pytest.raises(SystemExit):
        cli.lint(bad)


def test_1_3_2_lint_catches_schema_and_graph_errors(terminal):
    """Catches: unregistered section, unknown key, missing-node dependency, cycle,
    self-dependency, and `needs_root` on a subtable header."""

    def reject(builder: RecipeBuilder) -> None:
        with pytest.raises(RecipeRejected):
            Totchef(builder, terminal).lint()

    reject(RecipeBuilder().declares("nosuch", packages=[]))  # unregistered section
    reject(RecipeBuilder().declares("file", "f", path="/x", content="a", typo=1))  # unknown key
    reject(RecipeBuilder().declares("bash", "a", apply="x", depends_on=["ghost"]))  # missing node
    reject(RecipeBuilder().declares("bash", "a", apply="x", depends_on=["bash.a"]))  # self-dependency

    cyclic = RecipeBuilder()
    cyclic.declares("bash", "a", apply="x", depends_on=["bash.b"])
    cyclic.declares("bash", "b", apply="y", depends_on=["bash.a"])
    reject(cyclic)  # cycle

    header = RecipeBuilder()
    header.declares("bash", needs_root=True)
    header.declares("bash", "s", apply="x")
    reject(header)  # needs_root on a subtable header


def test_1_3_3_lint_needs_no_root_and_changes_nothing(recipe, terminal, totchef, tmp_path):
    """Linting needs no root and changes nothing."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    totchef.lint()  # returns cleanly

    assert not (tmp_path / "f").exists()
    assert terminal.commands == []  # no shell ran at all


# 1.4 Find out which recipe will be used


def test_1_4_1_where_prints_resolved_recipe_path(tmp_path, capsys):
    """`totchef where` prints the resolved recipe path and exits."""
    recipe_path = tmp_path / "recipe.toml"
    recipe_path.write_text("")

    cli.where(recipe_path)

    assert str(recipe_path) in capsys.readouterr().out


def test_1_4_2_recipe_discovery_follows_fixed_precedence(tmp_path, monkeypatch):
    """Precedence: --recipe/-r, $TOTCHEF_RECIPE, walk up for recipe.toml,
    ~/.config/totchef/recipe.toml, /etc/totchef/recipe.toml."""
    explicit = tmp_path / "explicit.toml"
    explicit.write_text("")
    assert find_recipe(explicit) == explicit.resolve()  # an explicit flag wins

    env_recipe = tmp_path / "env.toml"
    env_recipe.write_text("")
    monkeypatch.setenv(RECIPE_ENV, str(env_recipe))
    assert find_recipe(None) == env_recipe.resolve()  # then $TOTCHEF_RECIPE
    monkeypatch.delenv(RECIPE_ENV)

    project = tmp_path / "project"
    (project / "sub").mkdir(parents=True)
    (project / "recipe.toml").write_text("")
    monkeypatch.chdir(project / "sub")
    assert find_recipe(None) == (project / "recipe.toml").resolve()  # then walk up from cwd


def test_1_4_3_no_recipe_found_lists_searched_locations(tmp_path, monkeypatch):
    """When no recipe is found, the error lists every location searched."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    monkeypatch.delenv(RECIPE_ENV, raising=False)

    with pytest.raises(SystemExit) as miss:
        find_recipe(None)

    assert "Looked in" in str(miss.value)
    assert "recipe.toml" in str(miss.value)


# 1.5 Discover available cooks


def test_1_5_1_cooks_lists_section_scope_and_origin():
    """`totchef cooks` prints section, scope (root/user), and origin (built-in /
    plugin:<dist> / local:<path>) for every resolvable cook."""
    registry = cook_registry()

    assert registry["apt_pkg"].needs_root is True  # root scope
    assert registry["url"].needs_root is False  # user scope
    assert registry["apt_pkg"].origin == "built-in"


def test_1_5_2_cooks_reflects_live_registry():
    """An installed plugin or a dropped-in local cook shows up immediately."""
    cooks_dir = config_cooks_dir()
    cooks_dir.mkdir(parents=True)
    (cooks_dir / "widget_cook.py").write_text(
        "from totchef.cook_base import StateCook, StateChangeOutcome, StateEntrySpec\n"
        "class WidgetEntry(StateEntrySpec):\n"
        "    value: str = ''\n"
        "class WidgetCook(StateCook):\n"
        "    entry_model = WidgetEntry\n"
        "    def get_current_state(self): return {}\n"
        "    def get_desired_state(self): return {}\n"
        "    def apply_resource(self, name): return StateChangeOutcome(changed=False)\n"
    )
    cook_registry.cache_clear()

    registry = cook_registry()

    assert "widget" in registry
    assert registry["widget"].origin.startswith("local:")


# 1.6 Check the version


def test_1_6_version_reports_installed_version(capsys):
    """`totchef --version` reports the installed version."""
    assert __version__ == "0.1.0"

    with pytest.raises(typer.Exit):
        cli.version_callback(True)

    assert f"totchef {__version__}" in capsys.readouterr().out
