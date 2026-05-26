"""User stories §6 — Safety, correctness, and trust.

One prose-style test per acceptance criterion in `user-stories.md` §6. The convergence
and failure-classification stories drive the real chef in-process; the escalation /
privilege-drop stories exercise the real `cli`/`harness` functions at their boundary.
"""

import os
import sys

import pytest

from framework import RecipeBuilder, RecipeRejected, Totchef
from totchef.cli import ensure_root
from totchef.harness import become_user
from totchef.logs import SHARED_LOG_ENV
from totchef.recipe import RECIPE_ENV

GIT_NEEDS_INSTALL = "git:\n  Installed: (none)\n  Candidate: 1:2.40\n  Version table:\n     1:2.40 500\n        500 http://archive noble/main amd64 Packages\n"


# 6.1 Trust that re-runs only change what drifted


def test_6_1_1_cooks_probe_and_act_only_on_the_difference(recipe, terminal, http, totchef, system, tmp_path):
    """Versioned cooks skip up-to-date packages; state cooks skip resources whose
    content hash already matches."""
    already = tmp_path / "already.conf"
    already.write_text("A\n")
    recipe.declares("cargo", packages=["ripgrep"])
    recipe.declares("file", "f", path=str(already), content="A\n")
    system.has("cargo", "cargo-binstall")
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')
    terminal.arrange("cargo install --list", "ripgrep v14.1.1:\n    rg\n")

    report = totchef.up()

    report.assert_shows("cargo.ripgrep", "unchanged")
    report.assert_shows("file.f", "unchanged")
    terminal.expect_not_ran("binstall")


def test_6_1_2_post_hooks_fire_only_on_actual_change(recipe, terminal, totchef, tmp_path):
    """post_hooks fire only on actual change, so refreshes don't run on no-op passes."""
    target = tmp_path / "unit.service"
    recipe.declares("file", "unit", path=str(target), content="[Unit]\n", post_hook="systemctl daemon-reload")

    totchef.up().assert_shows("file.unit", "applied")
    terminal.expect_ran("daemon-reload")

    terminal.reset()
    totchef.up().assert_shows("file.unit", "unchanged")
    terminal.expect_not_ran("daemon-reload")


# 6.2 Understand that totchef creates and updates but never prunes


def test_6_2_1_convergence_is_create_update_only_never_prunes(recipe, totchef, tmp_path):
    """Dropping an entry leaves prior artifacts in place; teardown is manual."""
    artifact = tmp_path / "drop-in.conf"
    recipe.declares("file", "drop_in", path=str(artifact), content="X\n")

    totchef.up().assert_shows("file.drop_in", "applied")
    assert artifact.exists()

    del recipe.config["file"]  # operator removes the entry from the recipe
    totchef.up().assert_succeeded()

    assert artifact.exists()  # the artifact is left in place — teardown is manual


# 6.3 Escalate to root only for the apply, and drop privilege otherwise


def test_6_3_1_up_re_execs_under_sudo_pinning_recipe_and_log(monkeypatch, tmp_path):
    """`totchef up` re-execs under sudo, pinning the resolved recipe path and shared
    log file across the boundary."""
    recipe_path = tmp_path / "recipe.toml"
    captured: dict = {}
    monkeypatch.setattr(os, "geteuid", lambda: 1000)  # not root yet
    monkeypatch.setattr(os, "execvp", lambda file, argv: captured.update(file=file, argv=argv))
    monkeypatch.setattr(sys, "argv", ["totchef", "up"])
    monkeypatch.delenv(RECIPE_ENV, raising=False)

    ensure_root(recipe_path)

    assert captured["file"] == "sudo"
    assert os.environ[RECIPE_ENV] == str(recipe_path)
    assert f"--preserve-env={SHARED_LOG_ENV},{RECIPE_ENV}" in captured["argv"]


def test_6_3_2_forked_child_drops_privilege_for_user_nodes(monkeypatch):
    """A needs_root child keeps root; every other child drops privilege to the
    invoking user and repoints HOME/USER/PATH."""
    monkeypatch.setattr(os, "geteuid", lambda: 1000)  # already unprivileged: nothing to drop
    home_before = os.environ.get("HOME")
    become_user()
    assert os.environ.get("HOME") == home_before

    monkeypatch.setattr(os, "geteuid", lambda: 0)  # root, but not launched via sudo
    monkeypatch.delenv("SUDO_USER", raising=False)
    with pytest.raises(SystemExit):
        become_user()


def test_6_3_3_plan_and_lint_never_escalate(recipe, terminal, totchef):
    """plan and lint never escalate."""
    recipe.declares("apt_pkg", packages=["git"])  # a root-scoped cook
    terminal.arrange("apt-cache policy git", GIT_NEEDS_INSTALL)

    totchef.plan().assert_shows("apt_pkg.git", "would install")
    terminal.expect_not_ran("nala")  # probed, but no privileged transaction

    totchef.lint()  # validates only — no shell, no root
    terminal.expect_not_ran("nala")


# 6.4 Distinguish recoverable failures from fatal ones


def test_6_4_1_hard_failure_aborts_the_apply_and_exits_1(recipe, terminal, totchef):
    """Hard failure aborts the apply and exits 1 (e.g. unavailable package, bash
    apply error, uv tool install failure)."""
    recipe.declares("bash", "broken", apply="false-cmd")
    recipe.declares("bash", "after", apply="echo done", depends_on=["bash.broken"])
    terminal.arrange("false-cmd", exit_code=1)

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_shows("bash.broken", "failed")
    terminal.expect_not_ran("echo done")  # apply aborted: the dependent never ran


def test_6_4_2_soft_failure_warns_finishes_and_exits_75(recipe, terminal, totchef, tmp_path):
    """Soft failure warns, finishes the run, exits 75 (e.g. snap refresh, post_hook,
    invalid JSON in a target file)."""
    target = tmp_path / "grub.cfg"
    recipe.declares("file", "grub", path=str(target), content="X\n", post_hook="update-grub-fails")
    recipe.declares("bash", "after", apply="echo done", depends_on=["file.grub"])
    terminal.arrange("update-grub-fails", exit_code=1)

    report = totchef.up()

    report.assert_soft_failed()
    report.assert_shows("file.grub", "post-failed")
    terminal.expect_ran("echo done")  # the run finished; the dependent still ran


def test_6_4_3_report_names_which_cooks_hard_or_soft_failed(recipe, terminal, totchef):
    """The end-of-run report names which cooks hard- or soft-failed."""
    recipe.declares("bash", "broken_step", apply="false-cmd")
    terminal.arrange("false-cmd", exit_code=1)

    report = totchef.up()

    report.assert_shows("bash.broken_step", "failed")
    assert "bash.broken_step" in report.report
    assert "failed" in report.report


# 6.5 Skip steps that shouldn't run right now


def test_6_5_1_pre_hook_nonzero_exit_skips_the_item(recipe, terminal, totchef, tmp_path):
    """A non-zero pre_hook exit skips the item (reported as `skipped`, not failed)."""
    target = tmp_path / "f.conf"
    recipe.declares("file", "f", path=str(target), content="X\n", pre_hook="test -e /run/should-apply")
    terminal.arrange("test -e /run/should-apply", exit_code=1)

    report = totchef.up()

    report.assert_succeeded()  # a guarded skip is benign, not a failure
    report.assert_shows("file.f", "skipped")
    assert not target.exists()


def test_6_5_2_cooks_compose_intrinsic_guards_with_pre_hook(recipe, terminal, totchef, home):
    """Cooks chain their own guards with the operator's pre_hook (e.g. Chromium's
    "browser not running" check)."""
    local_state = home / ".config/chromium/Local State"
    local_state.parent.mkdir(parents=True)
    local_state.write_text('{"browser": {"enabled_labs_experiments": []}}')
    recipe.declares("chromium_flags", "chromium", local_state=".config/chromium/Local State", local_state_flags=["x@1"], pre_hook="test -e /run/maintenance")
    terminal.arrange("test -e /run/maintenance", exit_code=1)  # operator's own guard fails

    report = totchef.up()

    report.assert_shows("chromium_flags.chromium", "skipped")
    terminal.expect_ran("pgrep -x chromium")  # intrinsic guard and...
    terminal.expect_ran("test -e /run/maintenance")  # ...operator guard chained into one


def test_6_5_3_hooks_only_valid_on_state_cook_sections(terminal):
    """Declaring pre_hook/post_hook on a versioned section fails the lint."""
    bad = Totchef(RecipeBuilder().declares("cargo", packages=["ripgrep"], pre_hook="test -e /x"), terminal)

    with pytest.raises(RecipeRejected):
        bad.lint()
