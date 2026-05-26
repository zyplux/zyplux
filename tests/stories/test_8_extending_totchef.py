"""User stories §8 — Extending totchef (cook authors).

One prose-style test per acceptance criterion in `user-stories.md` §8. These drive the
real registry resolution, cook base classes, the orchestrator's diff, and schema lint —
a local-cook drop-in is written under the temp `$HOME` and resolved for real.
"""

from totchef.cook_base import FileStateCook, PackageListCook, StateCook, VersionedCook
from totchef.cook_runner import run_state
from totchef.cooks.apt_pkg_root_cook import AptPkgCook
from totchef.cooks.cargo_cook import CargoCook
from totchef.cooks.file_cook import FileCook
from totchef.recipe_graph import build_nodes
from totchef.registry import config_cooks_dir, cook_registry
from totchef.schema_lint import find_schema_problems

LOCAL_COOK = (
    "from totchef.cook_base import StateChangeOutcome, StateCook, StateEntrySpec\n"
    "class {cls}Entry(StateEntrySpec):\n"
    "    value: str = ''\n"
    "class {cls}Cook(StateCook):\n"
    "    entry_model = {cls}Entry\n"
    "    def get_current_state(self): return {{}}\n"
    "    def get_desired_state(self): return {{}}\n"
    "    def apply_resource(self, name): return StateChangeOutcome(changed=False)\n"
)


# 8.1 Add a new configuration domain as a plugin


def test_8_1_1_cook_registered_under_entry_point_group_serves_its_section():
    """A CookBase subclass registered under the `totchef.cooks` entry-point group
    serves the section named by its entry-point; origin shows in `totchef cooks`."""
    entry = cook_registry()["apt_pkg"]

    assert entry.section == "apt_pkg"  # the entry-point name is the section it serves
    assert entry.cook is AptPkgCook
    assert entry.origin == "built-in"


# 8.2 Prototype a cook without packaging it


def test_8_2_1_local_cook_file_is_picked_up_and_shadows_a_builtin():
    """A loose ~/.config/totchef/cooks/<section>_cook.py is loaded as a local cook
    and shadows a built-in of the same name."""
    cooks_dir = config_cooks_dir()
    cooks_dir.mkdir(parents=True)
    (cooks_dir / "bash_cook.py").write_text(LOCAL_COOK.format(cls="ShadowBash"))
    cook_registry.cache_clear()

    entry = cook_registry()["bash"]

    assert entry.origin.startswith("local:")
    assert entry.cook.__name__ == "ShadowBashCook"  # shadows the built-in BashCook


# 8.3 Choose the right cook shape for my domain


def test_8_3_1_versioned_cook_implements_requested_installed_latest_sync():
    """VersionedCook: implement list_requested/list_installed/find_latest/sync;
    PackageListCook covers plain `packages = [...]` sections."""
    assert issubclass(CargoCook, PackageListCook)
    assert issubclass(PackageListCook, VersionedCook)

    cook = CargoCook({"packages": ["ripgrep", "just"]})
    assert cook.list_requested() == ["ripgrep", "just"]
    assert cook.unit_count == 2  # weighted by its package count


def test_8_3_2_state_cook_implements_current_desired_apply_filestate_diffs(tmp_path):
    """StateCook: implement get_current_state/get_desired_state/apply_resource;
    FileStateCook already diffs by sha256."""
    assert issubclass(FileCook, FileStateCook)
    assert issubclass(FileStateCook, StateCook)

    target = tmp_path / "f"
    target.write_text("X\n")
    matching = FileCook({"f": {"path": str(target), "content": "X\n"}})
    assert matching.get_current_state()["f"] == matching.get_desired_state()["f"]  # equal sha256 ⇒ no diff

    drifting = FileCook({"f": {"path": str(target), "content": "Y\n"}})
    assert drifting.get_current_state()["f"] != drifting.get_desired_state()["f"]


def test_8_3_3_cook_only_probes_and_acts_orchestrator_owns_the_diff(tmp_path):
    """The cook only probes and acts; the orchestrator owns every diff and
    idempotency decision."""
    settled = tmp_path / "settled"
    settled.write_text("SAME\n")
    matching = FileCook({"f": {"path": str(settled), "content": "SAME\n"}})
    assert matching.get_current_state() == matching.get_desired_state()  # the cook only reports state …

    # … the orchestrator (run_state) owns the diff and decides whether to act
    assert run_state(matching, "file", dry_run=False).rows[0].action == "unchanged"

    drift = tmp_path / "drift"
    drift.write_text("OLD\n")
    drifting = FileCook({"f": {"path": str(drift), "content": "NEW\n"}})
    assert run_state(drifting, "file", dry_run=False).rows[0].action == "applied"


# 8.4 Get a typo'd recipe rejected against my schema


def test_8_4_1_cook_entry_model_lints_recipe_slice_reporting_violations():
    """A cook's `entry_model` (pydantic, extra='forbid') is validated by lint, which
    reports every violation as a precise `[node] location: message` line."""
    typoed = {"file": {"x": {"path": "/x", "content": "a", "moed": "0644"}}}
    problems = find_schema_problems(typoed, build_nodes(typoed))

    assert any("[file.x]" in problem for problem in problems)
    assert any("moed" in problem for problem in problems)

    valid = {"file": {"x": {"path": "/x", "content": "a"}}}
    assert find_schema_problems(valid, build_nodes(valid)) == []
