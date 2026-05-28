"""User stories §2 — Authoring a recipe. One test per §2 criterion on the real chef: fan-out/ordering read off the plan, bad recipes via lint rejection."""

APT_CACHE_POLICY = """\
git:
  Installed: (none)
  Candidate: 1.0
  Version table:
     1.0 500
        500 http://archive.example stable/main amd64 Packages
"""


def _exec_line(desktop_file) -> str:
    return next(line for line in desktop_file.read_text().splitlines() if line.startswith("Exec="))


# 2.1 Declare the machine I want in one TOML file


def test_2_1_1_each_section_maps_to_a_cook_plain_vs_subtable(recipe, terminal, totchef):
    """A plain-data section is one unit of work; a subtable section fans out to one addressable unit per entry."""
    terminal.arrange("apt-cache policy", APT_CACHE_POLICY)
    recipe.declares("apt_pkg", packages=["git"])  # plain-data section: one domain unit
    recipe.declares("url", "bun", url="https://bun.sh/install")  # subtable …
    recipe.declares("url", "uv", url="https://astral.sh/uv")  # … one unit per entry

    plan = totchef.plan()

    plan.assert_shows("apt_pkg.git", "would install")  # the plain section's single domain
    plan.assert_shows("url.bun", "would install")  # the subtable fanned out …
    plan.assert_shows("url.uv", "would install")  # … into two independently addressable units


def test_2_1_2_operator_declares_desired_state_not_steps(recipe, totchef, tmp_path):
    """The operator writes only the desired end state; the tool computes diff and order."""
    target = tmp_path / "drop.conf"
    recipe.declares("file", "drop", path=str(target), content="GRUB_TIMEOUT=2\n")

    totchef.up().assert_shows("file.drop", "applied")  # the tool computes: absent → write
    totchef.up().assert_shows("file.drop", "unchanged")  # and: present == desired → no-op


# 2.2 Express ordering between resources


def test_2_2_1_depends_on_names_entry_node_or_section(recipe, terminal, totchef):
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


def test_2_2_2_resources_run_in_topological_order(recipe, terminal, totchef):
    """totchef builds a DAG; a node only starts once all dependencies have succeeded."""
    recipe.declares("bash", "first", apply="step-one")
    recipe.declares("bash", "second", apply="step-two", depends_on=["bash.first"])

    totchef.up().assert_succeeded()

    order = [command.line for command in terminal.commands]
    ran_first = next(i for i, line in enumerate(order) if "step-one" in line)
    ran_second = next(i for i, line in enumerate(order) if "step-two" in line)
    assert ran_first < ran_second


def test_2_2_3_bad_dependency_is_caught_at_lint(scenario, chef):
    """A missing-node dependency, a cycle, or a self-dependency is caught at lint."""
    chef(scenario().declares("bash", "a", apply="x", depends_on=["nope"])).lint().assert_rejected()

    chef(scenario().declares("bash", "a", apply="x", depends_on=["bash.a"])).lint().assert_rejected()

    cyclic = scenario()
    cyclic.declares("bash", "a", apply="x", depends_on=["bash.b"])
    cyclic.declares("bash", "b", apply="y", depends_on=["bash.a"])
    chef(cyclic).lint().assert_rejected()


# 2.3 Set shared defaults across a section's entries


def test_2_3_1_section_defaults_fold_into_entries_lists_extend_others_override(recipe, totchef, home, tmp_path):
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


def test_2_3_2_shared_desktop_features_yield_union_per_entry(recipe, totchef, home, tmp_path):
    """`[desktop]` shared `features` plus `[desktop.brave]` additions yield the union."""
    source = tmp_path / "brave.desktop"
    source.write_text("[Desktop Entry]\nExec=/usr/bin/brave %U\n")
    recipe.declares("desktop", features=["SharedFeature"])  # shared across the section
    recipe.config["desktop"]["brave"] = {"desktop": str(source), "features": ["BraveFeature"]}

    totchef.up().assert_shows("desktop.brave", "applied")

    assert "--enable-features=SharedFeature,BraveFeature" in _exec_line(home / ".local/share/applications/brave.desktop")


# 2.4 Grant root only where it's needed


def test_2_4_1_needs_root_per_entry_escalates_a_privilege_agnostic_cook(recipe, totchef):
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


def test_2_4_2_lint_forbids_needs_root_on_a_subtable_header(scenario, chef):
    """`needs_root` on a subtable header is forbidden (it would grant root wholesale); it must be per leaf entry, and the error says so."""
    wholesale = scenario()
    wholesale.declares("bash", needs_root=True)  # header-level grant
    wholesale.declares("bash", "step", apply="x")

    chef(wholesale).lint().assert_rejected("needs_root")
