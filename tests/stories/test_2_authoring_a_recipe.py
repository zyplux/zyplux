"""User stories §2 — Authoring a recipe.

One prose-style test per acceptance criterion in `user-stories.md` §2. The graph and
schema stories build the real DAG (`recipe_graph`) and validate against the real cook
schemas; the convergence stories drive the chef in-process.
"""

import pytest

from framework import RecipeBuilder, RecipeRejected, Totchef
from totchef.cooks.bash_cook import BashCook
from totchef.recipe_graph import build_node_graph, build_nodes, node_slice


# 2.1 Declare the machine I want in one TOML file


def test_2_1_1_each_section_maps_to_a_cook_plain_vs_subtable(recipe):
    """A plain-data section is one unit of work; a subtable section fans out to one
    unit per entry."""
    recipe.declares("apt_pkg", packages=["git", "curl"])  # plain-data section
    recipe.declares("url", "bun", url="https://bun.sh/install")  # subtable …
    recipe.declares("url", "uv", url="https://astral.sh/uv")  # … one node per entry

    nodes = build_nodes(recipe.config)

    assert nodes["apt_pkg"].entry is None  # one unit of work for the whole list
    assert nodes["url.bun"].entry == "bun"
    assert {"url.bun", "url.uv"} <= set(nodes)


def test_2_1_2_operator_declares_desired_state_not_steps(recipe, totchef, tmp_path):
    """The operator writes only the desired end state; the tool computes diff and order."""
    target = tmp_path / "drop.conf"
    recipe.declares("file", "drop", path=str(target), content="GRUB_TIMEOUT=2\n")

    totchef.up().assert_shows("file.drop", "applied")  # the tool computes: absent → write
    totchef.up().assert_shows("file.drop", "unchanged")  # and: present == desired → no-op


# 2.2 Express ordering between resources


def test_2_2_1_depends_on_names_entry_node_or_section(recipe):
    """`depends_on` can name an entry, a single-node section, or a whole section
    (which fans out to all its entries)."""
    recipe.declares("apt_pkg", packages=["git"])
    recipe.declares("apt_repo", "vendor", key_url="https://x", uris="https://y")
    recipe.declares("apt_repo", "other", key_url="https://x", uris="https://y")
    recipe.declares("bash", "prereqs", apply="x")
    recipe.declares("bash", "main", apply="y", depends_on=["bash.prereqs", "apt_pkg", "apt_repo"])

    deps = build_node_graph(build_nodes(recipe.config))["bash.main"]

    assert "bash.prereqs" in deps  # an entry
    assert "apt_pkg" in deps  # a single-node section
    assert {"apt_repo.vendor", "apt_repo.other"} <= deps  # a whole section fans out


def test_2_2_2_resources_run_in_topological_order(recipe, terminal, totchef):
    """totchef builds a DAG; a node only starts once all dependencies have succeeded."""
    recipe.declares("bash", "first", apply="step-one")
    recipe.declares("bash", "second", apply="step-two", depends_on=["bash.first"])

    totchef.up().assert_succeeded()

    order = [command.line for command in terminal.commands]
    ran_first = next(i for i, line in enumerate(order) if "step-one" in line)
    ran_second = next(i for i, line in enumerate(order) if "step-two" in line)
    assert ran_first < ran_second


def test_2_2_3_bad_dependency_is_caught_at_lint(terminal):
    """A missing-node dependency, a cycle, or a self-dependency is caught at lint
    with a fix-it message."""
    missing = Totchef(RecipeBuilder().declares("bash", "a", apply="x", depends_on=["nope"]), terminal)
    with pytest.raises(RecipeRejected):
        missing.lint()

    self_dep = Totchef(RecipeBuilder().declares("bash", "a", apply="x", depends_on=["bash.a"]), terminal)
    with pytest.raises(RecipeRejected):
        self_dep.lint()

    cyclic = RecipeBuilder()
    cyclic.declares("bash", "a", apply="x", depends_on=["bash.b"])
    cyclic.declares("bash", "b", apply="y", depends_on=["bash.a"])
    with pytest.raises(RecipeRejected):
        Totchef(cyclic, terminal).lint()


# 2.3 Set shared defaults across a section's entries


def test_2_3_1_section_defaults_fold_into_entries_lists_extend_others_override(recipe):
    """Section-level scalar/list keys become defaults; lists extend, everything
    else overrides."""
    recipe.declares("desktop", desktop="default.desktop", features=["Shared"])  # section-level defaults
    recipe.config["desktop"]["brave"] = {"desktop": "brave.desktop", "features": ["Extra"]}

    slice_ = node_slice(recipe.config, build_nodes(recipe.config)["desktop.brave"])

    assert slice_["desktop"] == "brave.desktop"  # a scalar: the entry overrides the default
    assert slice_["features"] == ["Shared", "Extra"]  # a list: the entry extends the default


def test_2_3_2_shared_desktop_features_yield_union_per_entry(recipe, totchef, home, tmp_path):
    """`[desktop]` shared `features` plus `[desktop.brave]` additions yield the union."""
    source = tmp_path / "brave.desktop"
    source.write_text("[Desktop Entry]\nExec=/usr/bin/brave %U\n")
    recipe.declares("desktop", features=["SharedFeature"])  # shared across the section
    recipe.config["desktop"]["brave"] = {"desktop": str(source), "features": ["BraveFeature"]}

    totchef.up().assert_shows("desktop.brave", "applied")

    override = home / ".local/share/applications/brave.desktop"
    exec_line = next(line for line in override.read_text().splitlines() if line.startswith("Exec="))
    assert "--enable-features=SharedFeature,BraveFeature" in exec_line


# 2.4 Grant root only where it's needed


def test_2_4_1_needs_root_per_entry_escalates_a_privilege_agnostic_cook(recipe):
    """A recipe entry can set `needs_root = true` to escalate a privilege-agnostic
    cook (bash, file) for that one entry."""
    recipe.declares("bash", "root_step", apply="x", needs_root=True)
    recipe.declares("file", "root_file", path="/etc/x.conf", content="a", needs_root=True)

    nodes = build_nodes(recipe.config)

    assert BashCook.needs_root is False  # the cook itself is privilege-agnostic …
    assert nodes["bash.root_step"].needs_root is True  # … escalated for this one entry
    assert nodes["file.root_file"].needs_root is True


def test_2_4_2_lint_forbids_needs_root_on_a_subtable_header(terminal):
    """`needs_root` on a subtable header is forbidden (it would grant root wholesale);
    it must be per leaf entry, and the error says so."""
    wholesale = RecipeBuilder()
    wholesale.declares("bash", needs_root=True)  # header-level grant
    wholesale.declares("bash", "step", apply="x")

    with pytest.raises(RecipeRejected) as rejected:
        Totchef(wholesale, terminal).lint()

    assert "needs_root" in str(rejected.value)
