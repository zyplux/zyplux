"""User stories §10 — Recipe linting rules. One test per rule, driving `lint` through the chef or the real CLI; a rejected recipe never touches the system."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from act_fixtures import Cli, Totchef
    from arrange_fixtures import FakeTerminal, RecipeBuilder

# 10.1 Validate a recipe without running it


def test_10_1_1_lint_validates_and_prints_path_valid(cli: Cli, tmp_path: Path) -> None:
    """`totchef lint` validates against every cook's schema and the graph, then prints `<path>: valid` or exits with a precise error."""
    good = tmp_path / "recipe.toml"
    good.write_text('[bash.step]\napply = "true"\n')

    cli.run("lint", "--recipe", str(good)).assert_prints(": valid")

    bad = tmp_path / "bad.toml"
    bad.write_text("[nosuchsection]\nx = 1\n")
    cli.run("lint", "--recipe", str(bad)).assert_failed()


def test_10_1_2_lint_needs_no_root_and_changes_nothing(recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, tmp_path: Path) -> None:
    """Linting needs no root and changes nothing — no file is written and no shell command runs."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    totchef.lint().assert_valid()  # returns cleanly

    assert not (tmp_path / "f").exists()
    assert terminal.commands == []  # no shell ran at all


# 10.2 Have structural mistakes rejected with a precise error


def test_10_2_1_every_section_names_a_registered_cook_and_every_key_is_known(
    scenario: Callable[[], RecipeBuilder], chef: Callable[[RecipeBuilder], Totchef]
) -> None:
    """A section must name a registered cook; an unknown or misspelled key is rejected (`extra='forbid'`) rather than silently ignored."""
    chef(scenario().declares("nosuch", packages=[])).lint().assert_rejected()  # unregistered section

    chef(scenario().declares("file", "f", path="/x", content="a", typo=1)).lint().assert_rejected()  # unknown key


def test_10_2_2_dependencies_name_existing_nodes_with_no_cycles_or_self_dependencies(
    scenario: Callable[[], RecipeBuilder], chef: Callable[[RecipeBuilder], Totchef]
) -> None:
    """A missing-node dependency, a cycle, or a self-dependency is rejected."""
    chef(scenario().declares("bash", "a", apply="x", depends_on=["nope"])).lint().assert_rejected()

    chef(scenario().declares("bash", "a", apply="x", depends_on=["bash.a"])).lint().assert_rejected()

    cyclic = scenario()
    cyclic.declares("bash", "a", apply="x", depends_on=["bash.b"])
    cyclic.declares("bash", "b", apply="y", depends_on=["bash.a"])
    chef(cyclic).lint().assert_rejected()


def test_10_2_3_needs_root_sits_on_a_leaf_entry_never_a_subtable_header(
    scenario: Callable[[], RecipeBuilder], chef: Callable[[RecipeBuilder], Totchef]
) -> None:
    """`needs_root` on a subtable header is forbidden (it would grant root wholesale); it must be per leaf entry, and the error says so."""
    wholesale = scenario()
    wholesale.declares("bash", needs_root=True)  # header-level grant
    wholesale.declares("bash", "step", apply="x")

    chef(wholesale).lint().assert_rejected("needs_root")


def test_10_2_4_remove_how_requires_remove_when(recipe: RecipeBuilder, totchef: Totchef) -> None:
    """`remove_how` without `remove_when` is an orphan instruction; lint rejects it naming the missing condition."""
    recipe.declares("bash", "orphan", apply="x", remove_how="delete me someday")

    totchef.lint().assert_rejected("remove_when")


# 10.3 Have cook contracts enforced statically


def test_10_3_1_bin_commands_embed_a_version_or_offer_help(
    recipe: RecipeBuilder,
    scenario: Callable[[], RecipeBuilder],
    chef: Callable[[RecipeBuilder], Totchef],
    totchef: Totchef,
    bundled_files: Path,
    tmp_path: Path,
) -> None:
    """A command that doesn't embed `__version__` or offer `--version`/`--help` can't enter a bin cook — lint rejects it statically, never executing it."""
    sentinel = tmp_path / "executed"
    (bundled_files / "naked.py").write_text(f'from pathlib import Path\n\nPath("{sentinel}").write_text("ran")\n')
    recipe.declares("usr_local_bin", "naked", source="naked.py")

    lint = totchef.lint()

    lint.assert_rejected("__version__")
    lint.assert_rejected("--version")
    lint.assert_rejected("--help")
    assert not sentinel.exists()  # the contract check reads the command, never runs it

    vetted = 'import argparse\n\n__version__ = "1.0.0"\n\nparser = argparse.ArgumentParser()\nparser.add_argument("--version", action="version", version=__version__)\n'
    (bundled_files / "vetted.py").write_text(vetted)
    good = scenario().declares("local_bin", "vetted", source="vetted.py")
    chef(good).lint().assert_valid()


def test_10_3_2_conf_entries_declare_exactly_one_of_line_or_lines(
    recipe: RecipeBuilder,
    scenario: Callable[[], RecipeBuilder],
    chef: Callable[[RecipeBuilder], Totchef],
    totchef: Totchef,
    tmp_path: Path,
) -> None:
    """An entry declares a single `line` or a `lines` array — declaring both, or neither, is rejected."""
    target = tmp_path / "c.conf"
    recipe.declares("conf", "both", target=str(target), line="a = 1", lines=["b = 2"])
    totchef.lint().assert_rejected("not both")

    neither = scenario().declares("conf", "neither", target=str(target))
    chef(neither).lint().assert_rejected("set `line` or `lines`")


def test_10_3_3_cook_entry_model_violations_are_reported_per_node_and_location(cli: Cli, tmp_path: Path) -> None:
    """A cook's `entry_model` (pydantic, extra='forbid') is validated by lint, which reports every violation as a precise `[node] location: message` line."""
    typoed = tmp_path / "typo.toml"
    typoed.write_text('[file.x]\npath = "/x"\ncontent = "a"\nmoed = "0644"\n')

    rejected = cli.run("lint", "--recipe", str(typoed))
    rejected.assert_failed()
    rejected.assert_prints("[file.x]")  # the precise node …
    rejected.assert_prints("moed")  # … and the offending key

    valid = tmp_path / "valid.toml"
    valid.write_text('[file.x]\npath = "/x"\ncontent = "a"\n')
    cli.run("lint", "--recipe", str(valid)).assert_prints(": valid")
