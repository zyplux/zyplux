"""User stories §8 — Observing a run. §8.1 report and §8.3.1 log ownership are observed end-to-end; §8.2/§8.3.2-3 scheduler/pump rendering stay white-box."""

import os
import threading

from rich.progress import MofNCompleteColumn, TimeElapsedColumn

import totchef.logs as log_internals
from totchef.cook_runner import format_queueing, format_unlocked
from totchef.logs import set_terminal_echo, write_log
from totchef.terminal import (
    ProgressHandle,
    _LiveProgress,
    _colorize_log_line,
    _runner_style,
    is_interactive,
    progress_region,
)


# 7.1 See a clear, color-coded report of what happened


def test_8_1_1_report_table_color_coded_on_terminal_plain_toon_otherwise(recipe, scenario, chef, terminal, totchef, tmp_path):
    """A table with cook-node/before/current/latest/action; rich color-coded on a terminal, plain TOON text on a non-terminal."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    plan = totchef.plan()
    assert '{"cook-node",before,current,latest,action}' in plan.report  # plain TOON off-terminal
    plan.assert_colored("would apply", "yellow")  # a pending change → yellow

    totchef.up().assert_colored("applied", "green")  # a change made → green

    boom = scenario().declares("bash", "boom", apply="explode")
    terminal.arrange("explode", exit_code=1)
    chef(boom).up().assert_colored("failed", "red bold")  # a failure → red


def test_8_1_2_up_shows_changed_rows_plus_footer_plan_shows_all(recipe, totchef, tmp_path):
    """A real up shows only changed/failed rows plus a footer (unchanged count, elapsed); a plan shows every row."""
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
    assert "1 unchanged" in report.report  # the footer summarizes what was left alone


def test_8_1_3_content_hash_diffs_humanized_present_or_stale(recipe, totchef, tmp_path):
    """A matching hash reads `present`, a drifting one reads `stale`."""
    drift = tmp_path / "drift"
    drift.write_text("OLD\n")  # exists but will be rewritten
    settled = tmp_path / "settled"
    settled.write_text("SAME\n")  # already matches
    recipe.declares("file", "drift", path=str(drift), content="NEW\n")
    recipe.declares("file", "settled", path=str(settled), content="SAME\n")

    plan = totchef.plan()

    assert "file.drift,stale,stale,present,would apply" in plan.report
    assert "file.settled,present,present,present,ok" in plan.report


def test_8_1_4_before_and_current_diverge_on_upgrade(recipe, terminal, http, totchef, system):
    """After an upgrade, `before` shows the pre-sync version and `current` shows the post-sync version, so the row reads as a real diff."""
    recipe.declares("url", "claude", url="https://claude.ai/install.sh", update_action=["update"])
    system.has("claude")
    terminal.arrange("claude --version", "2.1.152")  # pre-sync probe
    terminal.arrange("claude update", effect=lambda: terminal.arrange("claude --version", "2.1.153"))  # post-sync probe sees the new version

    report = totchef.up()

    report.assert_shows("url.claude", "upgraded")
    assert "url.claude,2.1.152,2.1.153,—,upgraded" in report.full_table  # before ≠ current after a real version bump


def test_8_1_5_failed_install_keeps_before_equal_current(recipe, terminal, http, totchef, system):
    """A failed install reads `before == current ≠ latest` — the row tells the operator the new version didn't land."""
    recipe.declares("uv", packages=["brokentool"])
    system.has("uv")
    http.arrange("pypi.org/pypi/brokentool/json", '{"info": {"version": "1.0"}}')
    terminal.arrange("uv tool list", "")  # nothing installed yet
    terminal.arrange("uv tool install brokentool", exit_code=1)  # the install errors

    report = totchef.up()

    report.assert_hard_failed()
    assert 'uv.brokentool,(none),(none),"1.0",failed' in report.full_table  # before == current, latest unmet


# 7.2 Watch progress while a long run executes


def test_8_2_1_transient_progress_bar_cleared_on_exit(monkeypatch):
    """An interactive progress bar shows completed/total and elapsed, cleared on exit, leaving logs above it."""
    assert is_interactive() is False  # the test console is not a terminal
    with progress_region("Cooking", total=3) as bar:
        assert type(bar) is ProgressHandle  # off-terminal: a no-op handle
        bar.advance()

    monkeypatch.setattr("totchef.terminal.is_interactive", lambda: True)
    with progress_region("Cooking", total=3) as live:
        assert isinstance(live, _LiveProgress)  # on a terminal: a live transient bar
        progress = live._progress
        column_types = {type(column) for column in progress.columns}
        assert MofNCompleteColumn in column_types  # the bar shows completed/total …
        assert TimeElapsedColumn in column_types  # … and elapsed time
        assert progress.tasks[0].total == 3  # over the run's resource count
        live.advance()
        assert progress.tasks[0].completed == 1  # advancing moves it forward
        assert progress.live.transient is True  # transient ⇒ cleared on exit, leaving the logs above it


def test_8_2_2_log_lines_colorized_and_tagged_per_cook():
    """Each cook's log lines are tagged with its name in a stable per-cook color so concurrent output stays readable."""
    first = _runner_style("url.bun")
    again = _runner_style("url.bun")
    other = _runner_style("apt_pkg")

    assert first == again  # stable across one cook's lines
    assert first != other  # distinct cooks get distinct hues

    colored = _colorize_log_line("[2026-05-27 10:00:00] url.bun                      INFO    Installing")
    assert "url.bun" in colored.plain  # the runner tag is carried into the rendered line


def test_8_2_3_start_and_completion_lines_announce_waits_and_unblocks():
    """Start lines announce who is running and what they wait on/unblock; completion lines report timing and what just unlocked."""
    queueing = format_queueing(("apt_pkg",), {"apt_pkg": 5}, combined=5)
    assert "queueing" in queueing and "apt_pkg" in queueing

    unlocked = format_unlocked(("apt_pkg",), {"apt_pkg": 2}, {"apt_pkg": 2})
    assert "unlocked" in unlocked and "apt_pkg (2/2)" in unlocked


# 7.3 Keep a timestamped log of every run


def test_8_3_1_timestamped_log_under_user_state_dir_chowned_back(apply_in_container):
    """A run's timestamped log under the user's state dir is chowned back, so the operator owns it though the apply ran as root. In a container."""
    run = apply_in_container('[file.f]\npath = "/home/tester/f"\ncontent = "x\\n"\n', ["/home/tester/f"])

    assert run.log_owner == "tester", run.transcript


def test_8_3_2_all_output_funnels_through_a_single_pump(monkeypatch, tmp_path):
    """Parent and every forked cook's stdout/stderr funnel through one pump so log lines never interleave with the live region."""
    log_file = tmp_path / "run.log"
    monkeypatch.setattr(log_internals, "LOG_HANDLE", open(log_file, "a"))  # noqa: SIM115 — the pump owns the handle for the run
    monkeypatch.setattr(log_internals, "ECHO_LOGS_TO_TERMINAL", True)
    emitted: list[str] = []
    monkeypatch.setattr(log_internals, "LINE_SINK", emitted.append)  # the terminal sink the pump feeds

    # the real pump: one thread draining the merged fd that parent and every forked cook write to
    read_fd, write_fd = os.pipe()
    pump = threading.Thread(target=log_internals._pump, args=(read_fd,))
    pump.start()
    with os.fdopen(write_fd, "w") as stream:  # two "cooks" interleaving their writes onto the one pipe
        stream.write("url.bun   installing\n")
        stream.write("apt_pkg   updating\n")
    pump.join(timeout=2)

    assert log_file.read_text() == "url.bun   installing\napt_pkg   updating\n"  # one ordered writer to the file
    assert emitted == ["url.bun   installing\n", "apt_pkg   updating\n"]  # one ordered sink to the terminal — never interleaved

    monkeypatch.setattr(log_internals, "LOG_HANDLE", None)
    write_log("dropped")  # no handle yet ⇒ a safe no-op


def test_8_3_3_dry_run_shows_only_plan_on_terminal_but_logs_everything(recipe, totchef, tmp_path, monkeypatch):
    """A dry run shows only the plan table on the terminal while still recording every line to the log file."""
    log_file = tmp_path / "run.log"
    monkeypatch.setattr(log_internals, "LOG_HANDLE", open(log_file, "a"))  # noqa: SIM115 — the pump owns the handle for the run
    monkeypatch.setattr(log_internals, "ECHO_LOGS_TO_TERMINAL", True)
    emitted: list[str] = []
    monkeypatch.setattr(log_internals, "LINE_SINK", emitted.append)

    set_terminal_echo(False)  # dry-run suppresses cook log echo to the terminal …
    assert log_internals.ECHO_LOGS_TO_TERMINAL is False
    log_internals._emit_terminal("cook chatter\n")  # what the pump would mirror for a cook's line
    write_log("cook chatter\n")

    assert emitted == []  # … nothing reached the terminal while echo was off …
    assert log_file.read_text() == "cook chatter\n"  # … yet the log file still recorded every line

    set_terminal_echo(True)
    assert log_internals.ECHO_LOGS_TO_TERMINAL is True

    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")
    plan = totchef.plan()
    assert '{"cook-node"' in plan.report  # and the plan table itself is still produced
