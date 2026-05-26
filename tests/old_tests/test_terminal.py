"""Terminal log coloring: each cook's name gets a stable palette hue (so its lines are trackable), while the message keeps its severity/state color."""

from totchef import terminal
from totchef.terminal import RUNNER_PALETTE, _line_style, _report_cell, _runner_style


def test_runner_color_is_stable_and_from_palette():
    assert _runner_style("apt_pkg") == _runner_style("apt_pkg")
    assert _runner_style("apt_pkg") in RUNNER_PALETTE


def test_cooks_seen_together_get_distinct_colors():
    runners = [f"cook{i}" for i in range(len(RUNNER_PALETTE))]
    assert len({_runner_style(r) for r in runners}) == len(RUNNER_PALETTE)


def test_message_style_tracks_state_then_severity():
    assert _line_style("ERROR", "boom") == "bold red"
    assert _line_style("WARNING", "post_hook failed") == "bold yellow"
    assert _line_style("INFO", "started; queueing: cargo") == "cornflower_blue"
    assert _line_style("INFO", "completed (4.213s)") == "green3"
    assert _line_style("INFO", "Done. Installed 13 package(s).") == ""


def test_report_cell_reads_as_a_diff():
    assert _report_cell("action", "would upgrade", "would upgrade").style == "yellow"
    assert _report_cell("latest", "0.2.1", "would upgrade").style == "yellow"
    assert _report_cell("latest", "present", "applied").style == "green"
    assert _report_cell("current", "0.2.0", "would upgrade").style == "dim"
    assert _report_cell("cook-node", "cargo.rumdl", "would upgrade").style == _runner_style("cargo.rumdl")


def test_colorize_keeps_runner_and_message_independently_colored():
    text = terminal._colorize_log_line("[2026-05-27 01:29:10] url.rustup                   ERROR   boom")
    spans = {text.plain[s.start : s.end]: s.style for s in text.spans}
    assert spans["url.rustup                   "] == _runner_style("url.rustup")
    assert spans["boom"] == "bold red"
