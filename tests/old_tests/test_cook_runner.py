"""The diff engine — chef's idempotency guarantee: run_versioned/run_state turn a cook's probes into the install/upgrade/unchanged/missing/failed verdict, with fakes for real cooks."""

import contextlib
import types

from totchef import cook_runner
from totchef.cook_base import (
    CookBase,
    CookResult,
    StateChangeOutcome,
    StateCook,
    SyncOutcome,
    VersionedCook,
)
from totchef.cook_runner import (
    build_dependents,
    build_reach,
    build_weights,
    format_duration,
    format_queueing,
    format_state,
    format_unlocked,
    format_version,
    log_completion,
    pick_worst_status,
    run_cook_guarded,
    run_state,
    run_versioned,
)
from totchef.recipe_graph import Node, build_nodes

HEX = "a" * 64
HEX2 = "b" * 64


# --- small formatters ---


def test_pick_worst_status_picks_highest_rank():
    assert pick_worst_status([]) == "ok"
    assert pick_worst_status(["ok", "soft_fail"]) == "soft_fail"
    assert pick_worst_status(["soft_fail", "hard_fail", "ok"]) == "hard_fail"


def test_format_version_dashes_when_empty():
    assert format_version(None) == "—"
    assert format_version("") == "—"
    assert format_version("1.2.3") == "1.2.3"


def test_format_state_hides_content_digest_as_present():
    assert format_state(HEX) == "present"
    assert format_state("absent") == "absent"
    assert format_state("configured") == "configured"


def test_format_duration_steps_up_at_each_natural_boundary():
    assert format_duration(0.001234) == "0.001234s"
    assert format_duration(4.213) == "4.213s"
    assert format_duration(59.99) == "59.99s"
    assert format_duration(60) == "1m 0s"
    assert format_duration(132.456) == "2m 12s"
    assert format_duration(3600) == "1h 0m"
    assert format_duration(3661) == "1h 1m"
    assert format_duration(86400) == "1d 0h"
    assert format_duration(90061) == "1d 1h"
    assert format_duration(36_000_000) == "416d 16h"


# --- run_versioned ---


class FakeVersioned(VersionedCook):
    def __init__(self, requested, before, after, latest, outcome=SyncOutcome("ok")):
        self._requested = requested
        self._before = before
        self._after = after
        self._latest = latest
        self._outcome = outcome
        self._installed_calls = 0
        self.synced: tuple[list[str], list[str]] | None = None

    def list_requested(self):
        return self._requested

    def list_installed(self):
        self._installed_calls += 1
        return self._before if self._installed_calls == 1 else self._after

    def find_latest(self, names):
        return self._latest

    def sync(self, to_install, to_upgrade):
        self.synced = (to_install, to_upgrade)
        return self._outcome


def test_run_versioned_dry_run_classifies_each_package():
    cook = FakeVersioned(
        requested=["new", "stale", "current", "noprobe"],
        before={"stale": "1.0", "current": "1.0", "noprobe": "2.0"},
        after={},
        latest={"new": "1.0", "stale": "2.0", "current": "1.0", "noprobe": None},
    )
    rows = {r.name: r for r in run_versioned(cook, "sec", dry_run=True).rows}
    assert (rows["new"].action, rows["new"].changed) == ("would install", True)
    assert (rows["stale"].action, rows["stale"].changed) == ("would upgrade", True)
    assert (rows["current"].action, rows["current"].changed) == ("up-to-date", False)
    assert (rows["noprobe"].action, rows["noprobe"].changed) == ("would sync", True)
    assert cook.synced is None  # dry run never syncs


def test_run_versioned_splits_install_from_upgrade_and_reports_outcome():
    cook = FakeVersioned(
        requested=["new", "stale", "current", "gone"],
        before={"stale": "1.0", "current": "1.0", "gone": "9"},
        after={"new": "1.0", "stale": "2.0", "current": "1.0"},
        latest={"new": None, "stale": "2.0", "current": "1.0", "gone": None},
    )
    result = run_versioned(cook, "sec", dry_run=False)
    rows = {r.name: r for r in result.rows}
    # to_install = absent; to_upgrade = present with a moved-or-unknown latest
    # (current, whose latest equals installed, is excluded).
    assert cook.synced == (["new"], ["stale", "gone"])
    assert rows["new"].action == "installed"
    assert rows["stale"].action == "upgraded"
    assert rows["current"].action == "unchanged"
    assert rows["gone"].action == "missing"  # requested, still absent, run ok
    assert result.status == "ok"


def test_run_versioned_marks_absent_after_hard_fail_as_failed():
    cook = FakeVersioned(
        requested=["pkg"],
        before={},
        after={},
        latest={"pkg": None},
        outcome=SyncOutcome("hard_fail", "boom"),
    )
    result = run_versioned(cook, "sec", dry_run=False)
    assert result.status == "hard_fail"
    assert result.rows[0].action == "failed"
    assert result.message == "boom"


# --- run_state ---


class FakeState(StateCook):
    def __init__(self, current, desired, outcomes=None, hooks=None):
        self._current = current
        self._desired = desired
        self._outcomes = outcomes or {}
        self._hooks = hooks or {}
        self.applied: list[str] = []

    def list_resources(self):
        return list(self._desired)

    def get_current_state(self):
        return self._current

    def get_desired_state(self):
        return self._desired

    def get_hooks(self, name):
        return self._hooks.get(name, (None, None))

    def apply_resource(self, name):
        self.applied.append(name)
        return self._outcomes.get(name, StateChangeOutcome(changed=True))


def test_run_state_dry_run_flags_changes_and_stale_digests():
    cook = FakeState(
        current={"add": "absent", "same": "present", "edit": HEX},
        desired={"add": "present", "same": "present", "edit": HEX2},
    )
    rows = {r.name: r for r in run_state(cook, "sec", dry_run=True).rows}
    assert (rows["add"].action, rows["add"].changed) == ("would apply", True)
    assert (rows["same"].action, rows["same"].changed) == ("ok", False)
    assert rows["edit"].action == "would apply"
    assert rows["edit"].installed == "stale"  # a changing content digest reads as 'stale'
    assert cook.applied == []  # dry run never applies


def test_run_state_applies_only_drifted_resources():
    cook = FakeState(
        current={"drift": "absent", "ok": "present"},
        desired={"drift": "present", "ok": "present"},
    )
    rows = {r.name: r for r in run_state(cook, "sec", dry_run=False).rows}
    assert cook.applied == ["drift"]
    assert rows["drift"].action == "applied"  # past-tense mirror of the plan's "would apply"
    assert rows["ok"].action == "unchanged"


def test_run_state_end_report_mirrors_plan_columns():
    # A drifting digest reads "stale" and the desired state fills `latest` in the
    # end report exactly as in the plan — only the action verb shifts to past tense.
    cook = FakeState(current={"edit": HEX}, desired={"edit": HEX2})
    end = {r.name: r for r in run_state(cook, "sec", dry_run=False).rows}["edit"]
    plan = {r.name: r for r in run_state(cook, "sec", dry_run=True).rows}["edit"]
    assert (end.installed, end.latest) == (plan.installed, plan.latest) == ("stale", "present")
    assert (plan.action, end.action) == ("would apply", "applied")


def test_run_state_skips_when_pre_hook_is_not_satisfied(monkeypatch):
    monkeypatch.setattr(cook_runner, "run_pre_hook", lambda snippet: False)
    cook = FakeState(
        current={"x": "absent"},
        desired={"x": "present"},
        hooks={"x": ("guard-cmd", None)},
    )
    result = run_state(cook, "sec", dry_run=False)
    assert cook.applied == []
    assert result.rows[0].action == "skipped"
    assert result.status == "ok"


def test_run_state_post_hook_failure_downgrades_to_soft_fail(monkeypatch):
    monkeypatch.setattr(cook_runner, "run_post_hook", lambda snippet: "soft_fail")
    cook = FakeState(
        current={"x": "absent"},
        desired={"x": "present"},
        outcomes={"x": StateChangeOutcome(changed=True)},
        hooks={"x": (None, "refresh-cmd")},
    )
    result = run_state(cook, "sec", dry_run=False)
    assert result.rows[0].action == "post-failed"
    assert result.status == "soft_fail"


def test_run_state_apply_hard_fail_is_reported():
    cook = FakeState(
        current={"x": "absent"},
        desired={"x": "present"},
        outcomes={"x": StateChangeOutcome(changed=False, status="hard_fail", message="nope")},
    )
    result = run_state(cook, "sec", dry_run=False)
    assert result.rows[0].action == "failed"
    assert result.status == "hard_fail"


def test_run_state_post_hook_is_skipped_when_apply_made_no_change(monkeypatch):
    ran_post = False

    def record(snippet):
        nonlocal ran_post
        ran_post = True
        return "ok"

    monkeypatch.setattr(cook_runner, "run_post_hook", record)
    # Drift triggers apply, but apply reports changed=False, so post_hook must not run.
    cook = FakeState(
        current={"x": "absent"},
        desired={"x": "present"},
        outcomes={"x": StateChangeOutcome(changed=False)},
        hooks={"x": (None, "refresh-cmd")},
    )
    result = run_state(cook, "sec", dry_run=False)
    assert ran_post is False
    assert result.rows[0].action == "unchanged"


# --- run_cook_guarded start line ---


@contextlib.contextmanager
def null_context(_runner):
    yield


def make_node(node_id, *, needs_root, depends_on):
    return Node(node_id, node_id.split(".")[0], None, needs_root, depends_on)


def recording_logger(monkeypatch):
    """Capture logged lines and neuter cook_context."""
    lines: list[str] = []
    logger = types.SimpleNamespace(info=lines.append, warning=lines.append, error=lines.append)
    monkeypatch.setattr(cook_runner, "logger", logger)
    monkeypatch.setattr(cook_runner, "cook_context", null_context)
    return lines


def capture_start_line(node, monkeypatch, dependents=(), reach=None, weights=None, dry_run=False):
    """Return run_cook_guarded's start line with euid/user and the cook body stubbed."""
    lines = recording_logger(monkeypatch)
    monkeypatch.setattr(cook_runner.os, "geteuid", lambda: 4242)
    monkeypatch.setattr(cook_runner.pwd, "getpwuid", lambda _uid: types.SimpleNamespace(pw_name="alice"))
    monkeypatch.setattr(cook_runner, "run_cook", lambda n, _c, _d: CookResult(n.id, "ok", []))
    run_cook_guarded(node, {}, dry_run, dependents=dependents, reach=reach, weights=weights)
    return lines[0]


def test_start_line_appends_depends_on_for_user_node(monkeypatch):
    node = make_node("url.rustup", needs_root=False, depends_on=("apt_pkg", "bash.prereqs"))
    assert capture_start_line(node, monkeypatch) == ("started as alice; depends_on apt_pkg, bash.prereqs")


def test_start_line_omits_depends_on_for_root_node(monkeypatch):
    node = make_node("apt_repo", needs_root=True, depends_on=("apt_pkg",))
    assert capture_start_line(node, monkeypatch) == "started as alice"


def test_start_line_appends_queueing_dependants(monkeypatch):
    node = make_node("apt_pkg", needs_root=False, depends_on=())
    line = capture_start_line(node, monkeypatch, dependents=("url.rustup", "cargo"))
    assert line == "started as alice; queueing: url.rustup, cargo"


def test_start_line_combines_depends_on_and_queueing(monkeypatch):
    node = make_node("bash.step", needs_root=False, depends_on=("apt_pkg",))
    line = capture_start_line(node, monkeypatch, dependents=("snap",))
    assert line == "started as alice; depends_on apt_pkg; queueing: snap"


def test_start_line_drops_username_in_dry_run(monkeypatch):
    node = make_node("url.bun", needs_root=False, depends_on=())
    assert capture_start_line(node, monkeypatch, dry_run=True) == "started"


def test_start_line_queueing_annotates_each_dependant_with_reach(monkeypatch):
    node = make_node("bash.apt_prereqs", needs_root=False, depends_on=())
    line = capture_start_line(
        node,
        monkeypatch,
        dependents=("apt_pkg", "desktop.brave"),
        reach={"apt_pkg": 40, "desktop.brave": 1},
    )
    assert line == "started as alice; queueing: apt_pkg (40), desktop.brave"


def test_start_line_queueing_leads_with_deduplicated_combined_weight(monkeypatch):
    node = make_node("bash.apt_prereqs", needs_root=False, depends_on=())
    line = capture_start_line(
        node,
        monkeypatch,
        dependents=("apt_repo.brave", "apt_repo.vscode"),
        reach={"bash.apt_prereqs": 29, "apt_repo.brave": 24, "apt_repo.vscode": 24},
        weights={"bash.apt_prereqs": 1},
    )
    assert line == ("started as alice; queueing (28) : apt_repo.brave (24), apt_repo.vscode (24)")


# --- log_completion (parent-side completion line) ---


def test_completion_success_with_no_dependants_is_bare(monkeypatch):
    lines = recording_logger(monkeypatch)
    log_completion("cargo", CookResult("cargo", "ok", []), (), {}, {}, 4.213)
    assert lines[0] == "completed (4.213s)"


def test_completion_failure_blocks_dependants(monkeypatch):
    lines = recording_logger(monkeypatch)
    log_completion(
        "apt_pkg",
        CookResult("apt_pkg", "hard_fail", [], "boom"),
        ("cargo",),
        {"cargo": 1},
        {"cargo": 1},
        0.5072,
    )
    assert lines[0] == "completed with failure (0.5072s): boom; blocked: cargo"


def test_completion_success_carries_unlock_tally(monkeypatch):
    lines = recording_logger(monkeypatch)
    log_completion(
        "bash.ubuntu_pin",
        CookResult("bash.ubuntu_pin", "ok", []),
        ("apt_pkg",),
        {"apt_pkg": 7},
        {"apt_pkg": 7},
        1.234,
    )
    assert lines[0] == "completed (1.234s); unlocked: apt_pkg (7/7)"


# --- format_unlocked (shared-dependency tally) ---


def test_format_unlocked_omits_count_for_single_blocker_dependant():
    suffix = format_unlocked(
        ("desktop.brave", "desktop.code"),
        {"desktop.brave": 1, "desktop.code": 1},
        {"desktop.brave": 1, "desktop.code": 1},
    )
    assert suffix == "; unlocked: desktop.brave, desktop.code"


def test_format_unlocked_counts_blockers_of_a_shared_dependant():
    assert format_unlocked(("apt_pkg",), {"apt_pkg": 3}, {"apt_pkg": 7}) == ("; unlocked: apt_pkg (3/7)")


def test_format_unlocked_mixes_counted_and_bare_dependants():
    suffix = format_unlocked(
        ("apt_pkg", "desktop.brave"),
        {"apt_pkg": 2, "desktop.brave": 1},
        {"apt_pkg": 7, "desktop.brave": 1},
    )
    assert suffix == "; unlocked: apt_pkg (2/7), desktop.brave"


def test_format_unlocked_tracks_a_shared_dependant_across_completions():
    blocker_count = {"apt_pkg": 7}
    satisfied = {"apt_pkg": 0}
    seen = []
    for _ in range(7):
        satisfied["apt_pkg"] += 1
        seen.append(format_unlocked(("apt_pkg",), satisfied, blocker_count))
    assert seen[0] == "; unlocked: apt_pkg (1/7)"
    assert seen[-1] == "; unlocked: apt_pkg (7/7)"


def test_format_unlocked_empty_for_no_dependants():
    assert format_unlocked((), {}, {}) == ""


# --- format_queueing (reach annotation on the start line) ---


def test_format_queueing_omits_both_counts_for_lone_unit_dependant():
    assert format_queueing(("desktop.brave",), {"desktop.brave": 1}, 1) == ("; queueing: desktop.brave")


def test_format_queueing_annotates_a_high_reach_dependant():
    assert format_queueing(("apt_pkg",), {"apt_pkg": 40}, 40) == ("; queueing (40) : apt_pkg (40)")


def test_format_queueing_leads_with_combined_then_per_dependant_reach():
    suffix = format_queueing(("apt_pkg", "snap"), {"apt_pkg": 40, "snap": 1}, 41)
    assert suffix == "; queueing (41) : apt_pkg (40), snap"


def test_format_queueing_empty_for_no_dependants():
    assert format_queueing((), {}, 0) == ""


# --- build_weights / build_reach (work weight and recursive gating) ---


def test_unit_count_defaults_to_one_and_scales_with_versioned_packages():
    assert CookBase({}).unit_count == 1
    versioned = FakeVersioned(requested=["a", "b", "c"], before={}, after={}, latest={})
    assert versioned.unit_count == 3


def test_build_weights_reads_each_node_unit_count():
    config = {"snap": {"packages": ["alpha", "beta"]}}
    nodes = build_nodes(config)
    assert build_weights(config, nodes) == {"snap": 2}


def test_build_reach_sums_own_weight_plus_downstream():
    dependents = {"base": ("leaf", "mid"), "mid": ("leaf",), "leaf": ()}
    weights = {"base": 1, "mid": 1, "leaf": 1}
    assert build_reach(dependents, weights) == {"base": 3, "mid": 2, "leaf": 1}


def test_build_reach_counts_a_shared_dependant_once():
    dependents = {
        "prereq": ("repo_a", "repo_b"),
        "repo_a": ("apt_pkg",),
        "repo_b": ("apt_pkg",),
        "apt_pkg": (),
    }
    weights = {"prereq": 1, "repo_a": 1, "repo_b": 1, "apt_pkg": 30}
    reach = build_reach(dependents, weights)
    assert reach == {"prereq": 33, "repo_a": 31, "repo_b": 31, "apt_pkg": 30}


# --- build_dependents (scheduler prioritization) ---


def test_build_dependents_reverses_the_graph():
    graph = {
        "base": set(),
        "mid": {"base"},
        "leaf_a": {"base", "mid"},
        "leaf_b": set(),
    }
    assert build_dependents(graph) == {
        "base": ("leaf_a", "mid"),
        "mid": ("leaf_a",),
        "leaf_a": (),
        "leaf_b": (),
    }


def test_reach_orders_unblocking_nodes_first():
    graph = {"base": set(), "mid": {"base"}, "leaf": {"base", "mid"}}
    dependents = build_dependents(graph)
    reach = build_reach(dependents, dict.fromkeys(graph, 1))
    ready = ["leaf", "base", "mid"]
    assert sorted(ready, key=lambda n: reach[n], reverse=True) == [
        "base",
        "mid",
        "leaf",
    ]
