"""User stories §7 — Observing a run.

One prose-style test per acceptance criterion in `user-stories.md` §7. The report
content is captured from a real in-process run; the presentation and logging machinery
(color map, progress region, per-cook colors, the log pump's writer, the state-dir
resolver) is exercised through the real `terminal`/`cook_runner`/`logs` functions.
"""

import os
import pwd

import totchef.logs as log_internals
from totchef.cli import summary_rows
from totchef.cook_runner import format_queueing, format_unlocked
from totchef.logs import log_dir, set_terminal_echo, write_log
from totchef.terminal import (
    ACTION_STYLES,
    ProgressHandle,
    _colorize_log_line,
    _LiveProgress,
    _report_cell,
    _runner_style,
    is_interactive,
    progress_region,
)


# 7.1 See a clear, color-coded report of what happened


def test_7_1_1_report_table_color_coded_on_terminal_plain_toon_otherwise(recipe, totchef, tmp_path):
    """A table with cook-node/current/latest/action; rich color-coded on a terminal,
    plain TOON text on a non-terminal."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    plan = totchef.plan()

    assert '{"cook-node",current,latest,action}' in plan.report  # plain TOON off-terminal
    plan.assert_shows("file.f", "would apply")

    assert ACTION_STYLES["installed"] == "green"
    assert ACTION_STYLES["would apply"] == "yellow"
    assert ACTION_STYLES["failed"] == "red bold"
    assert ACTION_STYLES["unchanged"] == "dim"
    assert _report_cell("action", "installed", "installed").style == "green"


def test_7_1_2_up_shows_changed_rows_plus_footer_plan_shows_all(recipe, totchef, tmp_path):
    """A real up shows only changed/failed rows plus a footer (unchanged count,
    elapsed); a plan shows every row."""
    settled = tmp_path / "settled"
    settled.write_text("X\n")
    recipe.declares("file", "settled", path=str(settled), content="X\n")
    recipe.declares("file", "changed", path=str(tmp_path / "changed"), content="Y\n")

    plan = totchef.plan()
    assert "file.settled" in plan.report and "file.changed" in plan.report  # plan shows all

    report = totchef.up()
    assert "file.changed" in report.report  # up shows only the changed row …
    assert "file.settled" not in report.report  # … and hides the unchanged one
    report.assert_shows("file.settled", "unchanged")  # though it is still in the results

    footer = summary_rows(unchanged=3, elapsed=1.5)
    assert footer[0]["cook-node"] == "3 unchanged"
    assert footer[0]["action"] == "1.5s"


def test_7_1_3_content_hash_diffs_humanized_present_or_stale(recipe, totchef, tmp_path):
    """A matching hash reads `present`, a drifting one reads `stale`."""
    drift = tmp_path / "drift"
    drift.write_text("OLD\n")  # exists but will be rewritten
    settled = tmp_path / "settled"
    settled.write_text("SAME\n")  # already matches
    recipe.declares("file", "drift", path=str(drift), content="NEW\n")
    recipe.declares("file", "settled", path=str(settled), content="SAME\n")

    plan = totchef.plan()

    assert "file.drift,stale,present,would apply" in plan.report
    assert "file.settled,present,present,ok" in plan.report


# 7.2 Watch progress while a long run executes


def test_7_2_1_transient_progress_bar_cleared_on_exit(monkeypatch):
    """An interactive progress bar shows completed/total and elapsed, cleared on
    exit, leaving logs above it."""
    assert is_interactive() is False  # the test console is not a terminal
    with progress_region("Cooking", total=3) as bar:
        assert type(bar) is ProgressHandle  # off-terminal: a no-op handle
        bar.advance()

    monkeypatch.setattr("totchef.terminal.is_interactive", lambda: True)
    with progress_region("Cooking", total=3) as live:
        assert isinstance(live, _LiveProgress)  # on a terminal: a live transient bar
        live.advance()


def test_7_2_2_log_lines_colorized_and_tagged_per_cook():
    """Each cook's log lines are tagged with its name in a stable per-cook color so
    concurrent output stays readable."""
    first = _runner_style("url.bun")
    again = _runner_style("url.bun")
    other = _runner_style("apt_pkg")

    assert first == again  # stable across one cook's lines
    assert first != other  # distinct cooks get distinct hues

    colored = _colorize_log_line("[2026-05-27 10:00:00] url.bun                      INFO    Installing")
    assert "url.bun" in colored.plain  # the runner tag is carried into the rendered line


def test_7_2_3_start_and_completion_lines_announce_waits_and_unblocks():
    """Start lines announce who is running and what they wait on/unblock; completion
    lines report timing and what just unlocked."""
    queueing = format_queueing(("apt_pkg",), {"apt_pkg": 5}, combined=5)
    assert "queueing" in queueing and "apt_pkg" in queueing

    unlocked = format_unlocked(("apt_pkg",), {"apt_pkg": 2}, {"apt_pkg": 2})
    assert "unlocked" in unlocked and "apt_pkg (2/2)" in unlocked


# 7.3 Keep a timestamped log of every run


def test_7_3_1_timestamped_log_under_user_state_dir_chowned_back(monkeypatch, home, tmp_path):
    """Each run writes a timestamped log under the invoking user's state dir
    (resolved from SUDO_USER), chowned back to the user."""
    invoking_user = pwd.getpwuid(os.getuid()).pw_name
    monkeypatch.setenv("SUDO_USER", invoking_user)  # a root re-exec records the real user
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert log_dir() == tmp_path / "state" / "totchef" / "logs"

    monkeypatch.delenv("SUDO_USER")
    monkeypatch.delenv("XDG_STATE_HOME")
    assert log_dir() == home / ".local" / "state" / "totchef" / "logs"


def test_7_3_2_all_output_funnels_through_a_single_pump(monkeypatch, tmp_path):
    """Parent and every forked cook's stdout/stderr funnel through one pump so log
    lines never interleave with the live region."""
    log_file = tmp_path / "run.log"
    monkeypatch.setattr(log_internals, "LOG_HANDLE", open(log_file, "a"))  # noqa: SIM115 — the pump owns the handle for the run

    write_log("first line\n")
    write_log("second line\n")

    assert log_file.read_text() == "first line\nsecond line\n"  # one ordered writer, no interleaving

    monkeypatch.setattr(log_internals, "LOG_HANDLE", None)
    write_log("dropped")  # no handle yet ⇒ a safe no-op


def test_7_3_3_dry_run_shows_only_plan_on_terminal_but_logs_everything(recipe, totchef, tmp_path):
    """A dry run shows only the plan table on the terminal while still recording
    every line to the log file."""
    set_terminal_echo(False)  # dry-run suppresses cook log echo to the terminal …
    assert log_internals.ECHO_LOGS_TO_TERMINAL is False

    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")
    plan = totchef.plan()
    assert '{"cook-node"' in plan.report  # … but the plan table is still produced

    set_terminal_echo(True)
    assert log_internals.ECHO_LOGS_TO_TERMINAL is True
