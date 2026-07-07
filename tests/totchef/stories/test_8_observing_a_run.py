(
    """User stories §8 — Observing a run. §8.1 report and §8.3.1 log ownership are observed end-to-end; §8.2 rendering and §8.3.2's pump logic go """
    """through their own public seams (rich's Progress, log_pump's pump_lines/emit_terminal) rather than reaching into totchef's private helpers."""
)

import io
import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    import pytest
    from act_fixtures import Totchef
    from arrange_fixtures import FakeHttp, FakeSystem, FakeTerminal, RecipeBuilder
    from container_fixtures import ContainerRun

# 7.1 See a clear, color-coded report of what happened


def test_8_1_1_report_table_color_coded_on_terminal_plain_toon_otherwise(
    scenario: Callable[[], RecipeBuilder],
    chef: Callable[[RecipeBuilder], Totchef],
    terminal: FakeTerminal,
    totchef: Totchef,
) -> None:
    """A table with cook-node/before/current/latest/action; rich color-coded on a terminal, plain TOON text on a non-terminal."""
    totchef.recipe.declares("file", "f", path=str(totchef.workdir / "f"), content="X\n")

    plan = totchef.plan()
    assert '{"cook-node",before,current,latest,action}' in plan.report  # plain TOON off-terminal
    plan.assert_colored("would apply", "yellow")  # a pending change → yellow

    totchef.up().assert_colored("applied", "green")  # a change made → green

    boom = scenario().declares("bash", "boom", apply="explode")
    terminal.arrange("explode", exit_code=1)
    chef(boom).up().assert_colored("failed", "red bold")  # a failure → red


def test_8_1_2_up_shows_changed_rows_plus_footer_plan_shows_all(recipe: RecipeBuilder, totchef: Totchef, tmp_path: Path) -> None:
    """A real up shows only changed/failed rows plus a footer (unchanged count, elapsed); a plan shows every row."""
    settled = tmp_path / "settled"
    settled.write_text("X\n")
    recipe.declares("file", "settled", path=str(settled), content="X\n")
    recipe.declares("file", "changed", path=str(tmp_path / "changed"), content="Y\n")

    plan = totchef.plan()
    assert "file.settled" in plan.report  # plan shows all …
    assert "file.changed" in plan.report  # … every row

    report = totchef.up()
    assert "file.changed" in report.report  # up shows only the changed row …
    assert "file.settled" not in report.report  # … and hides the unchanged one
    report.assert_shows("file.settled", "unchanged")  # though it is still in the results
    assert "1 unchanged" in report.report  # the footer summarizes what was left alone


def test_8_1_3_content_hash_diffs_humanized_matches_or_differs(recipe: RecipeBuilder, totchef: Totchef, tmp_path: Path) -> None:
    """A hash equal to the rendered recipe content reads `matches`, a drifting one `differs`, a missing file `absent`; `latest` carries the short content id."""
    drift = tmp_path / "drift"
    drift.write_text("OLD\n")  # exists but will be rewritten
    settled = tmp_path / "settled"
    settled.write_text("SAME\n")  # already matches
    recipe.declares("file", "drift", path=str(drift), content="NEW\n")
    recipe.declares("file", "settled", path=str(settled), content="SAME\n")
    recipe.declares("file", "fresh", path=str(tmp_path / "fresh"), content="NEW\n")

    plan = totchef.plan()

    assert "file.drift,differs,differs,#21998928,would apply" in plan.report  # #sha256("NEW\n")[:8]
    assert "file.settled,matches,matches,#e4426b0f,ok" in plan.report  # #sha256("SAME\n")[:8]
    assert "file.fresh,absent,absent,#21998928,would apply" in plan.report

    report = totchef.up()

    assert "file.drift,differs,matches,#21998928,applied" in report.full_table
    assert "file.fresh,absent,matches,#21998928,applied" in report.full_table


def test_8_1_4_before_and_current_diverge_on_upgrade(recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem) -> None:
    """After an upgrade, `before` shows the pre-sync version and `current` shows the post-sync version, so the row reads as a real diff."""
    recipe.declares("url", "claude", url="https://claude.ai/install.sh", update_action=["update"])
    system.has("claude")
    terminal.arrange("claude --version", "2.1.152")  # pre-sync probe

    def _claude_now_updated() -> None:
        terminal.arrange("claude --version", "2.1.153")

    terminal.arrange("claude update", effect=_claude_now_updated)  # post-sync probe sees the new version

    report = totchef.up()

    report.assert_shows("url.claude", "upgraded")
    assert "url.claude,2.1.152,2.1.153,—,upgraded" in report.full_table  # before ≠ current after a real version bump


def test_8_1_5_failed_install_keeps_before_equal_current(
    recipe: RecipeBuilder, terminal: FakeTerminal, http: FakeHttp, totchef: Totchef, system: FakeSystem
) -> None:
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


def test_8_2_1_transient_progress_bar_cleared_on_exit(monkeypatch: pytest.MonkeyPatch, terminal_internals: ModuleType) -> None:
    """An interactive progress bar shows completed/total and elapsed, cleared on exit, leaving logs above it."""
    resource_count = 3
    assert terminal_internals.is_interactive() is False  # the test console is not a terminal
    with terminal_internals.progress_region("Cooking", total=resource_count) as bar:
        assert type(bar) is terminal_internals.ProgressHandle  # off-terminal: a no-op handle
        bar.advance()

    live_progresses: list[Progress] = []
    real_progress = terminal_internals.Progress

    def spy_progress(*args: object, **kwargs: object) -> Progress:
        """Build the real rich Progress `progress_region` would, keeping a handle on it — rich's Progress is public even where totchef's wrapper isn't."""
        instance = real_progress(*args, **kwargs)
        live_progresses.append(instance)
        return instance

    monkeypatch.setattr(terminal_internals, "Progress", spy_progress)
    monkeypatch.setattr("totchef.terminal.is_interactive", lambda: True)
    with terminal_internals.progress_region("Cooking", total=resource_count) as live:
        assert type(live) is not terminal_internals.ProgressHandle  # on a terminal: a live transient bar, not the no-op handle
        progress = live_progresses[-1]  # the real rich Progress progress_region built for this run
        column_types = {type(column) for column in progress.columns}
        assert MofNCompleteColumn in column_types  # the bar shows completed/total …
        assert TimeElapsedColumn in column_types  # … and elapsed time
        assert progress.tasks[0].total == resource_count  # over the run's resource count
        live.advance()
        assert progress.tasks[0].completed == 1  # advancing moves it forward
        assert progress.live.transient is True  # transient ⇒ cleared on exit, leaving the logs above it


def test_8_2_2_log_lines_colorized_and_tagged_per_cook(monkeypatch: pytest.MonkeyPatch, log_internals: ModuleType, terminal_internals: ModuleType) -> None:
    """Each cook's log lines are tagged with its name in a stable per-cook color so concurrent output stays readable."""

    def render(line: str) -> str:
        """Drive the line through `LINE_SINK`, the pump's real terminal sink, onto a captured console — the same path a pumped line takes."""
        buffer = io.StringIO()
        monkeypatch.setattr(terminal_internals, "console", lambda: Console(file=buffer, force_terminal=True, color_system="standard", width=200))
        log_internals.LINE_SINK(line)
        return buffer.getvalue()

    first = render("[2026-05-27 10:00:00] url.bun                      INFO    Installing")
    again = render("[2026-05-27 10:00:00] url.bun                      INFO    Installing")
    other = render("[2026-05-27 10:00:00] apt_pkg                      INFO    Installing")

    ansi_codes = re.compile(r"\x1b\[[0-9;]+m")
    assert ansi_codes.findall(first) == ansi_codes.findall(again)  # stable across one cook's lines
    assert ansi_codes.findall(first) != ansi_codes.findall(other)  # distinct cooks get distinct hues
    assert "url.bun" in first  # the runner tag is carried into the rendered line


def test_8_2_3_start_and_completion_lines_announce_waits_and_unblocks(cook_runner_internals: ModuleType) -> None:
    """Start lines announce who is running and what they wait on/unblock; completion lines report timing and what just unlocked."""
    queueing = cook_runner_internals.format_queueing(("apt_pkg",), {"apt_pkg": 5}, combined=5)
    assert "queueing" in queueing
    assert "apt_pkg" in queueing

    unlocked = cook_runner_internals.format_unlocked(("apt_pkg",), {"apt_pkg": 2}, {"apt_pkg": 2})
    assert "unlocked" in unlocked
    assert "apt_pkg (2/2)" in unlocked


# 7.3 Keep a timestamped log of every run


def test_8_3_1_timestamped_log_under_user_state_dir_chowned_back(apply_in_container: Callable[[str, list[str]], ContainerRun]) -> None:
    """A run's timestamped log under the user's state dir is chowned back, so the operator owns it though the apply ran as root. In a container."""
    run = apply_in_container('[file.f]\npath = "/home/tester/f"\ncontent = "x\\n"\n', ["/home/tester/f"])

    assert run.log_owner == "tester", run.transcript


def test_8_3_2_all_output_funnels_through_a_single_pump(tmp_path: Path, log_pump: ModuleType) -> None:
    """Parent and every forked cook's stdout/stderr funnel through one pump: every line reaches the file and the terminal, in order, except a drain marker."""
    log_file = tmp_path / "run.log"
    emitted: list[str] = []
    marker_event = threading.Event()
    drain_events: dict[str, threading.Event] = {"marker": marker_event}

    with log_file.open("a", encoding="utf-8") as handle:

        def write_log(line: str) -> None:
            handle.write(line)

        log_pump.pump_lines(
            ["url.bun   installing\n", "apt_pkg   updating\n", "marker\n"],
            write_log=write_log,
            emit_terminal=emitted.append,
            drain_events=drain_events,
        )

    assert log_file.read_text() == "url.bun   installing\napt_pkg   updating\n"  # one ordered writer to the file
    assert emitted == ["url.bun   installing\n", "apt_pkg   updating\n"]  # one ordered sink to the terminal — never interleaved
    assert marker_event.is_set()  # a line matching a registered marker signals its event …
    assert "marker" not in drain_events  # … and is popped once consumed, not written or mirrored like a real log line


def test_8_3_2_2_write_log_is_a_safe_no_op_before_a_run_opens_a_handle(monkeypatch: pytest.MonkeyPatch, log_internals: ModuleType) -> None:
    """write_log tolerates being called before any run has opened a log handle, rather than raising."""
    monkeypatch.setattr(log_internals.log_state, "log_handle", None)
    log_internals.write_log("dropped")  # no handle yet ⇒ a safe no-op


def test_8_3_3_dry_run_shows_only_plan_on_terminal_but_logs_everything(
    recipe: RecipeBuilder, totchef: Totchef, monkeypatch: pytest.MonkeyPatch, log_internals: ModuleType, log_pump: ModuleType
) -> None:
    """A dry run shows only the plan table on the terminal while still recording every line to the log file."""
    log_file = totchef.workdir / "run.log"
    monkeypatch.setattr(log_internals.log_state, "log_handle", Path(log_file).open("a", encoding="utf-8"))  # noqa: SIM115 — the pump owns the handle for the run
    monkeypatch.setattr(log_internals.log_state, "echo_to_terminal", True)
    emitted: list[str] = []
    monkeypatch.setattr(log_internals, "LINE_SINK", emitted.append)

    log_internals.set_terminal_echo(enabled=False)  # dry-run suppresses cook log echo to the terminal …
    assert not log_internals.log_state.echo_to_terminal
    log_pump.emit_terminal(
        "cook chatter\n", enabled=log_internals.log_state.echo_to_terminal, sink=log_internals.LINE_SINK
    )  # what the pump would mirror
    log_internals.write_log("cook chatter\n")

    assert emitted == []  # … nothing reached the terminal while echo was off …
    assert log_file.read_text() == "cook chatter\n"  # … yet the log file still recorded every line

    log_internals.set_terminal_echo(enabled=True)
    assert log_internals.log_state.echo_to_terminal

    recipe.declares("file", "f", path=str(totchef.workdir / "f"), content="X\n")
    plan = totchef.plan()
    assert '{"cook-node"' in plan.report  # and the plan table itself is still produced


def test_8_3_4_a_failed_run_names_its_log_file(scenario: Callable[[], RecipeBuilder], chef: Callable[[RecipeBuilder], Totchef], terminal: FakeTerminal) -> None:
    """A failed run's final summary names the run's log file, so an operator who saw only the report knows which file to open for the captured error."""
    boom = scenario().declares("bash", "boom", apply="explode")
    terminal.arrange("explode", exit_code=1)

    report = chef(boom).up()

    report.assert_hard_failed()
    report.assert_logged("apply aborted; full log:")
    report.assert_logged(".log")


def test_8_3_5_every_run_logs_the_totchef_version_up_front(recipe: RecipeBuilder, totchef: Totchef, tmp_path: Path, totchef_version: str) -> None:
    """Every plan/up logs `totchef <version>` first, naming the exact build behind any log file or scrollback."""
    recipe.declares("file", "f", path=str(tmp_path / "f"), content="X\n")

    for run in (totchef.plan(), totchef.up()):
        run.assert_logged(f"totchef {totchef_version}")
        assert f"totchef {totchef_version}" in run.logs.splitlines()[0]


# 8.4 See follow-up actions after the report


def test_8_4_1_delayed_messages_print_after_the_report_labeled_by_cook_node(recipe: RecipeBuilder, totchef: Totchef, tmp_path: Path) -> None:
    """A cook's delayed_message is logged live, then repeated in an `Action required` block after the report, labeled by cook node; none for a dry run."""
    source = tmp_path / "brave.desktop"
    source.write_text("[Desktop Entry]\nExec=/usr/bin/brave %U\n")
    recipe.declares("desktop", "brave", desktop=str(source), switches=["use-gl=egl"])

    plan = totchef.plan()
    assert "Action required" not in plan.terminal_report  # a dry run applies nothing, so no follow-ups

    report = totchef.up()

    report.assert_logged("Restart the app to apply the new Exec= line.")  # still emitted live during the session
    shown = report.terminal_report
    assert shown.index("Report") < shown.index("Action required")  # the block follows the report table
    block = shown.split("Action required", 1)[1]
    assert "desktop.brave" in block  # labeled with the cook node that asks for it
    assert "Restart the app to apply the new Exec= line." in block

    rerun = totchef.up()
    assert "Action required" not in rerun.terminal_report  # nothing changed, nothing to follow up
