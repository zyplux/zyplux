"""Story: justpty runs a `just` recipe under a PTY, teeing the transcript to a per-run log."""

from __future__ import annotations

import os
import signal
from typing import TYPE_CHECKING

from clipy import justpty

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest
    from typer.testing import CliRunner

FAKE_JUST_EXIT_CODE = 7

# 1.1 wrapping just so every run is logged


def test_1_1_1_forwards_arbitrary_recipe_args_and_propagates_the_exit_code(
    fake_just: Callable[[str], Path], tmp_path: Path
) -> None:
    fake_just(f'echo "just-args: $*"\nexit {FAKE_JUST_EXIT_CODE}')

    status = justpty.run_just(["hello", "--list"])

    assert status == FAKE_JUST_EXIT_CODE
    log_text = (tmp_path / "logs" / "just.log").read_text()
    assert "just hello --list" in log_text
    assert "just-args: hello --list" in log_text
    assert f"=== exit {FAKE_JUST_EXIT_CODE}" in log_text


def test_1_1_2_announces_the_log_path_and_points_logs_just_log_at_the_latest_run(
    fake_just: Callable[[str], Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_just("exit 0")

    justpty.run_just(["c"])

    announced = capsys.readouterr().err.strip().removeprefix("» log: ")
    run_log = tmp_path / announced
    assert run_log.is_file()
    symlink = tmp_path / "logs" / "just.log"
    assert symlink.is_symlink()
    assert symlink.resolve() == run_log


def test_1_1_3_prunes_all_but_the_newest_run_logs(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    names = [f"just-20260101-{i:06d}-1.log" for i in range(justpty.KEPT_RUN_LOGS + 5)]
    for name in names:
        (logs_dir / name).write_text("x")

    justpty.prune_stale_logs(logs_dir)

    remaining = sorted(path.name for path in logs_dir.glob("just-*.log"))
    assert remaining == sorted(names)[-justpty.KEPT_RUN_LOGS :]


# 1.2 the version flag and a missing just binary


def test_1_2_1_version_flag_prints_the_version_and_exits_cleanly(cli: CliRunner) -> None:
    result = cli.invoke(justpty.app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == justpty.__version__


def test_1_2_2_a_missing_just_binary_fails_fast_with_a_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))  # empty dir: no `just` anywhere
    monkeypatch.chdir(tmp_path)

    status = justpty.run_just(["c"])

    assert status == justpty.JUST_MISSING_EXIT
    assert "just not found on PATH" in capsys.readouterr().err
    assert not (tmp_path / "logs").exists()


# 1.3 keeping the transcript greppable across control sequences


def test_1_3_1_carriage_return_overwrites_replay_as_the_final_line() -> None:
    cleaner = justpty.TranscriptCleaner()

    output = cleaner.feed(b"abc\rXY\n") + cleaner.flush()

    assert output == "XYc\n"


def test_1_3_2_backspaces_erase_characters_like_a_real_progress_bar() -> None:
    cleaner = justpty.TranscriptCleaner()

    output = cleaner.feed(b"hello world\x08\x08\x08\x08\x08bug\n") + cleaner.flush()

    assert output == "hello bugld\n"


def test_1_3_3_erase_in_line_clears_a_redrawn_progress_message() -> None:
    cleaner = justpty.TranscriptCleaner()

    output = cleaner.feed(b"progress: 10%\x1b[2K\rprogress: 90%\n") + cleaner.flush()

    assert output == "progress: 90%\n"


def test_1_3_4_cursor_motion_escapes_flush_the_pending_line() -> None:
    cleaner = justpty.TranscriptCleaner()

    output = cleaner.feed(b"line one") + cleaner.feed(b"\x1b[1;1H") + cleaner.feed(b"line two\n") + cleaner.flush()

    assert output == "line one\nline two\n"


def test_1_3_5_stray_oscs_and_charset_switches_are_swallowed_rather_than_logged() -> None:
    assert justpty.TranscriptCleaner().feed(b"\x1b]0;title\x07next\n") == "next\n"
    assert justpty.TranscriptCleaner().feed(b"\x1b]0;title\x1b\\next\n") == "next\n"
    assert justpty.TranscriptCleaner().feed(b"\x1b(Bnext\n") == "next\n"
    assert justpty.TranscriptCleaner().feed(b"\x1bXnext\n") == "next\n"


def test_1_3_6_cursor_movement_escapes_reposition_the_write_column() -> None:
    assert justpty.TranscriptCleaner().feed(b"ab\x1b[5Cc\n") == "ab     c\n"
    assert justpty.TranscriptCleaner().feed(b"abcdef\x1b[3Dxy\n") == "abcxyf\n"
    assert justpty.TranscriptCleaner().feed(b"abcdef\x1b[2Gxy\n") == "axydef\n"


def test_1_3_7_erase_in_line_clears_exactly_the_requested_span() -> None:
    assert justpty.TranscriptCleaner().feed(b"abcdef\x1b[3G\x1b[0Kxy\n") == "abxy\n"
    assert justpty.TranscriptCleaner().feed(b"abcdef\x1b[3G\x1b[1Kxy\n") == "  xyef\n"


# 1.4 watching descriptors and forwarding resize/interrupt signals


def test_1_4_1_a_closed_descriptor_is_reported_as_unwatchable() -> None:
    assert justpty.watchable(0)
    assert not justpty.watchable(-1)


def test_1_4_2_a_non_tty_master_fd_does_not_crash_the_winsize_copy(tmp_path: Path) -> None:
    fd = os.open(tmp_path / "not-a-tty", os.O_CREAT | os.O_WRONLY)
    try:
        justpty.copy_winsize(fd)
    finally:
        os.close(fd)


def test_1_4_3_forwarded_signals_relay_to_the_childs_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "killpg", lambda pgid, signum: killed.append((pgid, signum)))
    fd = os.open(tmp_path / "not-a-tty", os.O_CREAT | os.O_WRONLY)

    try:
        justpty.forward_signals(child_pid=4321, master_fd=fd)
        sigint_handler = signal.getsignal(signal.SIGINT)
        sigwinch_handler = signal.getsignal(signal.SIGWINCH)
        assert callable(sigint_handler)
        assert callable(sigwinch_handler)
        sigint_handler(signal.SIGINT, None)
        sigwinch_handler(signal.SIGWINCH, None)
    finally:
        os.close(fd)

    assert killed == [(4321, signal.SIGINT)]
