"""User stories §2 — Authoring a recipe. One test per §2 criterion on the real chef: fan-out, ordering, and defaults read off the plan and the run."""

from pathlib import Path

from act_fixtures import Totchef
from arrange_fixtures import FakeSystem, FakeTerminal, RecipeBuilder

APT_CACHE_POLICY = """\
git:
  Installed: (none)
  Candidate: 1.0
  Version table:
     1.0 500
        500 http://archive.example stable/main amd64 Packages
"""


def _exec_line(desktop_file: Path) -> str:
    return next(line for line in desktop_file.read_text().splitlines() if line.startswith("Exec="))


# 2.1 Declare the machine I want in one TOML file


def test_2_1_1_each_section_maps_to_a_cook_plain_vs_subtable(recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef) -> None:
    """A plain-data section is one unit of work; a subtable section fans out to one addressable unit per entry."""
    terminal.arrange("apt-cache policy", APT_CACHE_POLICY)
    recipe.declares("apt_pkg", packages=["git"])  # plain-data section: one domain unit
    recipe.declares("url", "bun", url="https://bun.sh/install")  # subtable …
    recipe.declares("url", "uv", url="https://astral.sh/uv")  # … one unit per entry

    plan = totchef.plan()

    plan.assert_shows("apt_pkg.git", "would install")  # the plain section's single domain
    plan.assert_shows("url.bun", "would install")  # the subtable fanned out …
    plan.assert_shows("url.uv", "would install")  # … into two independently addressable units


def test_2_1_2_operator_declares_desired_state_not_steps(recipe: RecipeBuilder, totchef: Totchef, tmp_path: Path) -> None:
    """The operator writes only the desired end state; the tool computes diff and order."""
    target = tmp_path / "drop.conf"
    recipe.declares("file", "drop", path=str(target), content="GRUB_TIMEOUT=2\n")

    totchef.up().assert_shows("file.drop", "applied")  # the tool computes: absent → write
    totchef.up().assert_shows("file.drop", "unchanged")  # and: present == desired → no-op


def test_2_1_3_package_sections_split_into_named_entries(recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef) -> None:
    """A `packages = [...]` section can fan out like any subtable: each entry is its own node with its own packages and dependencies."""
    terminal.arrange("apt-cache policy", APT_CACHE_POLICY)
    recipe.declares("bash", "prereqs", apply="bootstrap-apt")
    recipe.declares("apt_pkg", "toolchain", packages=["git"], depends_on=["bash.prereqs"])
    recipe.declares("apt_pkg", "apps", packages=["blender"], depends_on=["apt_pkg.toolchain"])

    totchef.lint().assert_valid()

    plan = totchef.plan()

    plan.assert_shows("apt_pkg.git", "would install")  # the toolchain group's package …
    plan.assert_shows("apt_pkg.blender", "would install")  # … and the other group's, each from its own node
    plan.assert_ran_before("apt_pkg.git", "apt_pkg.blender")  # ordered by the entries' own depends_on


# 2.2 Express ordering between resources


def test_2_2_1_depends_on_names_entry_node_or_section(recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef) -> None:
    """`depends_on` can name an entry, a single-node section, or a whole section — which fans out so the dependant waits for every one of its entries."""
    terminal.arrange("apt-cache policy", APT_CACHE_POLICY)
    recipe.declares("apt_pkg", packages=["git"])
    recipe.declares("apt_repo", "vendor", key_url="https://x", uris="https://y")
    recipe.declares("apt_repo", "other", key_url="https://x", uris="https://y")
    recipe.declares("bash", "prereqs", apply="x")
    recipe.declares("bash", "main", apply="y", depends_on=["bash.prereqs", "apt_pkg", "apt_repo"])

    plan = totchef.plan()

    plan.assert_ran_before("bash.prereqs", "bash.main")  # an entry
    plan.assert_ran_before("apt_pkg.git", "bash.main")  # a single-node section
    plan.assert_ran_before("apt_repo.vendor", "bash.main")  # a whole section fans out …
    plan.assert_ran_before("apt_repo.other", "bash.main")  # … the dependant waits for every entry


def test_2_2_2_resources_run_in_topological_order(recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef) -> None:
    """totchef builds a DAG; a node only starts once all dependencies have succeeded."""
    recipe.declares("bash", "first", apply="step-one")
    recipe.declares("bash", "second", apply="step-two", depends_on=["bash.first"])

    totchef.up().assert_succeeded()

    order = [command.line for command in terminal.commands]
    ran_first = next(i for i, line in enumerate(order) if "step-one" in line)
    ran_second = next(i for i, line in enumerate(order) if "step-two" in line)
    assert ran_first < ran_second


# 2.3 Set shared defaults across a section's entries


def test_2_3_1_section_defaults_fold_into_entries_lists_extend_others_override(
    recipe: RecipeBuilder, totchef: Totchef, home: Path, tmp_path: Path
) -> None:
    """Section-level scalar/list keys become defaults; a list entry **extends** the shared list, while a scalar entry **overrides** the default."""
    shared = tmp_path / "shared.desktop"
    shared.write_text("[Desktop Entry]\nExec=/usr/bin/shared %U\n")
    brave = tmp_path / "brave.desktop"
    brave.write_text("[Desktop Entry]\nExec=/usr/bin/brave %U\n")
    recipe.declares("desktop", desktop=str(shared), features=["Shared"])  # section-level defaults
    recipe.config["desktop"]["brave"] = {"desktop": str(brave), "features": ["Extra"]}

    totchef.up().assert_shows("desktop.brave", "applied")

    line = _exec_line(home / ".local/share/applications/brave.desktop")
    assert "/usr/bin/brave" in line  # a scalar: the entry's source overrode the default
    assert "--enable-features=Shared,Extra" in line  # a list: the entry extended the default


def test_2_3_2_shared_desktop_features_yield_union_per_entry(recipe: RecipeBuilder, totchef: Totchef, home: Path, tmp_path: Path) -> None:
    """`[desktop]` shared `features` plus `[desktop.brave]` additions yield the union."""
    source = tmp_path / "brave.desktop"
    source.write_text("[Desktop Entry]\nExec=/usr/bin/brave %U\n")
    recipe.declares("desktop", features=["SharedFeature"])  # shared across the section
    recipe.config["desktop"]["brave"] = {"desktop": str(source), "features": ["BraveFeature"]}

    totchef.up().assert_shows("desktop.brave", "applied")

    assert "--enable-features=SharedFeature,BraveFeature" in _exec_line(home / ".local/share/applications/brave.desktop")


# 2.4 Grant root only where it's needed


def test_2_4_1_needs_root_per_entry_escalates_a_privilege_agnostic_cook(recipe: RecipeBuilder, totchef: Totchef) -> None:
    """A cook's `needs_root` sets privilege, but an entry may set `needs_root = true` to escalate a privilege-agnostic cook (`bash`, `file`) per entry."""
    recipe.declares("bash", "root_step", apply="x", needs_root=True)
    recipe.declares("bash", "user_step", apply="y")  # sibling entry, no grant
    recipe.declares("file", "root_file", path="/etc/x.conf", content="a", needs_root=True)

    totchef.lint().assert_valid()  # accepted: needs_root is a valid per-entry grant

    plan = totchef.plan()
    plan.assert_shows("bash.root_step", "would apply")  # the granted entries plan normally …
    plan.assert_shows("file.root_file", "would apply")
    plan.assert_shows("bash.user_step", "would apply")  # … alongside the ungranted sibling

    # the per-entry grant actually escalating only that entry (root writes its file, the sibling
    # writes as the invoking user) is verified end-to-end in the container — test_6_3_2.


# 2.5 Declare when a temporary entry expires


def test_2_5_1_remove_when_satisfied_surfaces_remove_how_in_action_required(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef
) -> None:
    """While `remove_when` exits non-zero (still waiting — a failing probe reads the same) the run is silent about it; once it exits 0 the `remove_how` instruction lands in the Action required block labeled with the node, on every run until the entry is deleted."""
    recipe.declares(
        "bash",
        "vaapi_fix",
        apply="install-shim",
        current_state="echo present",
        desired_state="present",
        remove_when="gh api repos/upstream/fix/pulls/430 --jq .merged | grep -qx true",
        remove_how="PR #430 merged — drop this workaround.",
    )
    terminal.arrange("echo present", "present")
    terminal.arrange("gh api", exit_code=1)  # upstream hasn't merged yet

    waiting = totchef.up()

    waiting.assert_succeeded()
    terminal.expect_ran("gh api")  # the probe did run …
    assert "Action required" not in waiting.terminal_report  # … but still-waiting stays silent

    terminal.arrange("gh api", exit_code=0)  # merged upstream

    fired = totchef.up()

    fired.assert_succeeded()
    fired.assert_logged("PR #430 merged")  # announced live during the run …
    block = fired.terminal_report.split("Action required", 1)[1]
    assert "bash.vaapi_fix" in block  # … and repeated after the report, labeled with the node
    assert "PR #430 merged" in block

    nag = totchef.up()
    assert "PR #430 merged" in nag.terminal_report  # keeps firing until the entry is removed


def test_2_5_2_plan_also_evaluates_remove_when(recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef) -> None:
    """A dry run evaluates the probes too — `plan` doubles as "check everything I'm waiting on" — and a watch without `remove_how` carries the generic removal notice."""
    recipe.declares("bash", "workaround", apply="install-it", remove_when="upstream-shipped-the-fix")

    plan = totchef.plan()

    plan.assert_succeeded()
    block = plan.terminal_report.split("Action required", 1)[1]
    assert "bash.workaround" in block
    assert "can be removed" in block  # no remove_how → the generic notice
    terminal.expect_not_ran("install-it")  # still a dry run: probed, never applied


def test_2_5_3_any_entry_or_plain_section_can_carry_remove_when(
    recipe: RecipeBuilder, terminal: FakeTerminal, system: FakeSystem, totchef: Totchef, tmp_path: Path
) -> None:
    """`remove_when`/`remove_how` sit on the base entry contract: a subtable entry and a plain-data section alike declare their expiry."""
    recipe.declares("file", "pin", path=str(tmp_path / "pin.conf"), content="pinned\n", remove_when="true", remove_how="pin obsolete")
    recipe.declares("uv", packages=[], remove_when="true", remove_how="section obsolete")
    system.has("uv")

    report = totchef.up()

    block = report.terminal_report.split("Action required", 1)[1]
    assert "file.pin" in block
    assert "pin obsolete" in block
    assert "section obsolete" in block
