"""User stories §9 — Extending totchef. One test per §9 criterion, each driving a real local-cook drop-in through `totchef` and asserting observable output."""

VERSIONED_COOK = """
from totchef import shell
from totchef.cook_base import PackageListCook, SyncOutcome


class GadgetCook(PackageListCook):
    def list_installed(self):
        return {name: "1.0" for name in getattr(self, "_installed", ())}

    def find_latest(self, names):
        return {name: "1.0" for name in names}

    def sync(self, to_install, to_upgrade):
        self._installed = list(to_install)
        for name in to_install:
            shell.run("install-gadget", name)
        return SyncOutcome("ok")
"""

FILE_STATE_COOK = """
from pathlib import Path

from totchef.cook_base import FileStateCook, StateChangeOutcome, EntrySpec


class NoteEntry(EntrySpec):
    path: str
    body: str = ""


class NoteCook(FileStateCook[NoteEntry]):
    entry_model = NoteEntry

    def _target_path(self, name):
        return Path(self.entries[name].path)

    def _render(self, name):
        return self.entries[name].body.encode()

    def apply_resource(self, name):
        target = Path(self.entries[name].path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.entries[name].body)
        return StateChangeOutcome(changed=True)
"""

PROBE_ONLY_COOK = """
from totchef import shell
from totchef.cook_base import StateChangeOutcome, StateCook, EntrySpec


class SwitchEntry(EntrySpec):
    current: str = ""
    desired: str = ""


class SwitchCook(StateCook[SwitchEntry]):
    entry_model = SwitchEntry

    def get_current_state(self):
        return {name: entry.current for name, entry in self.entries.items()}

    def get_desired_state(self):
        return {name: entry.desired for name, entry in self.entries.items()}

    def apply_resource(self, name):
        shell.run("flip-switch", name)
        return StateChangeOutcome(changed=True)
"""

SHADOW_BASH_COOK = """
from totchef.cook_base import StateChangeOutcome, StateCook, EntrySpec


class ShadowBashEntry(EntrySpec):
    apply: str = ""


class ShadowBashCook(StateCook[ShadowBashEntry]):
    entry_model = ShadowBashEntry

    def get_current_state(self):
        return {}

    def get_desired_state(self):
        return {}

    def apply_resource(self, name):
        return StateChangeOutcome(changed=False)
"""


def _drop_local_cook(home, filename: str, source: str) -> None:
    cooks_dir = home / ".config/totchef/cooks"
    cooks_dir.mkdir(parents=True, exist_ok=True)
    (cooks_dir / filename).write_text(source)


# 8.1 Add a new configuration domain as a plugin


def test_9_1_1_cook_registered_under_entry_point_group_serves_its_section(cli, register_plugin):
    """A CookBase subclass registered in the `totchef.cooks` entry-point group serves the section named by its entry-point; origin shows in `--list-cooks`."""
    cli.run("--list-cooks").assert_lists("apt_pkg", scope="root", origin="built-in")

    register_plugin("gadget", "acme-totchef-plugin")  # a third-party dist registers the same way as a built-in

    cli.run("--list-cooks").assert_lists("gadget", origin="plugin:acme-totchef-plugin")  # serves its section, origin reads plugin:<dist>


# 8.2 Prototype a cook without packaging it


def test_9_2_1_local_cook_file_is_picked_up_and_shadows_a_builtin(cli, home):
    """A loose ~/.config/totchef/cooks/<section>_cook.py is loaded as a local cook and shadows a built-in of the same name."""
    _drop_local_cook(home, "bash_cook.py", SHADOW_BASH_COOK)

    cli.run("--list-cooks").assert_lists("bash", origin="local")  # the built-in `bash` is now shadowed


# 8.3 Choose the right cook shape for my domain


def test_9_3_1_versioned_cook_implements_requested_installed_latest_sync(recipe, terminal, totchef, home):
    """VersionedCook: implement list_requested/list_installed/find_latest/sync; PackageListCook covers plain `packages = [...]` sections."""
    _drop_local_cook(home, "gadget_cook.py", VERSIONED_COOK)
    recipe.declares("gadget", packages=["alpha", "beta"])

    report = totchef.up()

    report.assert_succeeded()
    report.assert_shows("gadget.alpha", "installed")  # a plain `packages` list fans out …
    report.assert_shows("gadget.beta", "installed")
    terminal.expect_ran("install-gadget alpha")  # … and sync installs each requested package
    terminal.expect_ran("install-gadget beta")


def test_9_3_2_state_cook_implements_current_desired_apply_filestate_diffs(recipe, totchef, home, tmp_path):
    """StateCook: implement get_current_state/get_desired_state/apply_resource; FileStateCook already diffs by sha256."""
    _drop_local_cook(home, "note_cook.py", FILE_STATE_COOK)
    target = tmp_path / "note.txt"
    recipe.declares("note", "n", path=str(target), body="hello\n")

    totchef.up().assert_shows("note.n", "applied")  # absent → written
    assert target.read_text() == "hello\n"

    totchef.up().assert_shows("note.n", "unchanged")  # sha256 matches ⇒ no rewrite, for free


def test_9_3_3_cook_only_probes_and_acts_orchestrator_owns_the_diff(recipe, terminal, totchef, home):
    """The cook only probes and acts; the orchestrator owns every diff and idempotency decision."""
    _drop_local_cook(home, "switch_cook.py", PROBE_ONLY_COOK)
    recipe.declares("switch", "matched", current="on", desired="on")  # cook reports states …
    recipe.declares("switch", "drifted", current="off", desired="on")

    report = totchef.up()

    report.assert_shows("switch.matched", "unchanged")  # … chef diffs equal states → no act
    report.assert_shows("switch.drifted", "applied")  # … chef diffs differing states → act
    terminal.expect_not_ran("flip-switch matched")  # the cook's apply ran only where chef decided
    terminal.expect_ran("flip-switch drifted")


# 8.4 Get a typo'd recipe rejected against my schema


def test_9_4_1_cook_entry_model_lints_recipe_slice_reporting_violations(cli, tmp_path):
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
