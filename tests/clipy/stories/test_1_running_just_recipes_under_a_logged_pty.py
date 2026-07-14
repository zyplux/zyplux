"""Story: justpty runs a `just` recipe under a PTY, teeing the transcript to a per-run log."""

from __future__ import annotations

import io
import os
import shutil
import signal
import termios
from typing import TYPE_CHECKING

import clipy.justpty
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from typer.testing import CliRunner

FAKE_JUST_EXIT_CODE = 7

# 1.1 wrapping just so every run is logged


@pytest.mark.no_xdist
def test_1_1_1_forwards_arbitrary_recipe_args_and_propagates_the_exit_code(
    fake_just: Callable[[str], Path], tmp_path: Path
) -> None:
    fake_just(f'echo "just-args: $*"\nexit {FAKE_JUST_EXIT_CODE}')

    status = clipy.justpty.run_just(["hello", "--list"])

    assert status == FAKE_JUST_EXIT_CODE
    log_text = (tmp_path / "logs" / "just.log").read_text()
    assert "just hello --list" in log_text
    assert "just-args: hello --list" in log_text
    assert f"=== exit {FAKE_JUST_EXIT_CODE}" in log_text


@pytest.mark.no_xdist
def test_1_1_2_announces_the_log_path_and_points_logs_just_log_at_the_latest_run(
    fake_just: Callable[[str], Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_just("exit 0")

    clipy.justpty.run_just(["c"])

    announced = capsys.readouterr().err.strip().removeprefix("» log: ")
    run_log = tmp_path / announced
    assert run_log.is_file()
    symlink = tmp_path / "logs" / "just.log"
    assert symlink.is_symlink()
    assert symlink.resolve() == run_log


def test_1_1_3_prunes_all_but_the_newest_run_logs(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    names = [f"just-20260101-{i:06d}-1.log" for i in range(clipy.justpty.KEPT_RUN_LOGS + 5)]
    for name in names:
        (logs_dir / name).write_text("x")

    clipy.justpty.prune_stale_logs(logs_dir)

    remaining = sorted(path.name for path in logs_dir.glob("just-*.log"))
    assert remaining == sorted(names)[-clipy.justpty.KEPT_RUN_LOGS :]


# 1.2 the version flag and a missing just binary


def test_1_2_1_version_flag_prints_the_version_and_exits_cleanly(cli: CliRunner) -> None:
    result = cli.invoke(clipy.justpty.app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == clipy.justpty.__version__


def test_1_2_2_a_missing_just_binary_fails_fast_with_a_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))  # empty dir: no `just` anywhere
    monkeypatch.chdir(tmp_path)

    status = clipy.justpty.run_just(["c"])

    assert status == clipy.justpty.JUST_MISSING_EXIT
    assert "just not found on PATH" in capsys.readouterr().err
    assert not (tmp_path / "logs").exists()


# 1.3 keeping the transcript greppable across control sequences


def test_1_3_1_carriage_return_overwrites_replay_as_the_final_line() -> None:
    cleaner = clipy.justpty.TranscriptCleaner()

    output = cleaner.feed(b"abc\rXY\n") + cleaner.flush()

    assert output == "XYc\n"


def test_1_3_2_backspaces_erase_characters_like_a_real_progress_bar() -> None:
    cleaner = clipy.justpty.TranscriptCleaner()

    output = cleaner.feed(b"hello world\x08\x08\x08\x08\x08bug\n") + cleaner.flush()

    assert output == "hello bugld\n"


def test_1_3_3_erase_in_line_clears_a_redrawn_progress_message() -> None:
    cleaner = clipy.justpty.TranscriptCleaner()

    output = cleaner.feed(b"progress: 10%\x1b[2K\rprogress: 90%\n") + cleaner.flush()

    assert output == "progress: 90%\n"


def test_1_3_4_cursor_motion_escapes_flush_the_pending_line() -> None:
    cleaner = clipy.justpty.TranscriptCleaner()

    output = cleaner.feed(b"line one") + cleaner.feed(b"\x1b[1;1H") + cleaner.feed(b"line two\n") + cleaner.flush()

    assert output == "line one\nline two\n"


def test_1_3_5_stray_oscs_and_charset_switches_are_swallowed_rather_than_logged() -> None:
    assert clipy.justpty.TranscriptCleaner().feed(b"\x1b]0;title\x07next\n") == "next\n"
    assert clipy.justpty.TranscriptCleaner().feed(b"\x1b]0;title\x1b\\next\n") == "next\n"
    assert clipy.justpty.TranscriptCleaner().feed(b"\x1b(Bnext\n") == "next\n"
    assert clipy.justpty.TranscriptCleaner().feed(b"\x1bXnext\n") == "next\n"


def test_1_3_6_cursor_movement_escapes_reposition_the_write_column() -> None:
    assert clipy.justpty.TranscriptCleaner().feed(b"ab\x1b[5Cc\n") == "ab     c\n"
    assert clipy.justpty.TranscriptCleaner().feed(b"abcdef\x1b[3Dxy\n") == "abcxyf\n"
    assert clipy.justpty.TranscriptCleaner().feed(b"abcdef\x1b[2Gxy\n") == "axydef\n"


def test_1_3_7_erase_in_line_clears_exactly_the_requested_span() -> None:
    assert clipy.justpty.TranscriptCleaner().feed(b"abcdef\x1b[3G\x1b[0Kxy\n") == "abxy\n"
    assert clipy.justpty.TranscriptCleaner().feed(b"abcdef\x1b[3G\x1b[1Kxy\n") == "  xyef\n"


# 1.4 watching descriptors and forwarding resize/interrupt signals


def test_1_4_1_a_closed_descriptor_is_reported_as_unwatchable() -> None:
    assert clipy.justpty.watchable(0)
    assert not clipy.justpty.watchable(-1)


def test_1_4_2_a_non_tty_master_fd_does_not_crash_the_winsize_copy(tmp_path: Path) -> None:
    fd = os.open(tmp_path / "not-a-tty", os.O_CREAT | os.O_WRONLY)
    try:
        clipy.justpty.copy_winsize(fd)
    finally:
        os.close(fd)


def test_1_4_3_forwarded_signals_relay_to_the_childs_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "killpg", lambda pgid, signum: killed.append((pgid, signum)))
    fd = os.open(tmp_path / "not-a-tty", os.O_CREAT | os.O_WRONLY)

    try:
        clipy.justpty.forward_signals(child_pid=4321, master_fd=fd)
        sigint_handler = signal.getsignal(signal.SIGINT)
        sigwinch_handler = signal.getsignal(signal.SIGWINCH)
        assert callable(sigint_handler)
        assert callable(sigwinch_handler)
        sigint_handler(signal.SIGINT, None)
        sigwinch_handler(signal.SIGWINCH, None)
    finally:
        os.close(fd)

    assert killed == [(4321, signal.SIGINT)]


# 1.5 streaming pty bytes to the terminal and log without a real pty


def test_1_5_1_write_all_retries_until_every_byte_is_written() -> None:
    read_fd, write_fd = os.pipe()
    payload = b"x" * 1000

    clipy.justpty.write_all(write_fd, payload)

    os.close(write_fd)
    assert os.read(read_fd, len(payload) + 1) == payload
    os.close(read_fd)


def test_1_5_2_read_pty_returns_the_chunk_or_empty_bytes_once_the_fd_is_closed() -> None:
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"hi")
    os.close(write_fd)

    assert clipy.justpty.read_pty(read_fd) == b"hi"
    os.close(read_fd)
    assert clipy.justpty.read_pty(read_fd) == b""


def test_1_5_3_forward_stdin_relays_a_chunk_and_reports_eof_or_a_read_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    master_read, master_write = os.pipe()
    stdin_read, stdin_write = os.pipe()
    monkeypatch.setattr(clipy.justpty, "STDIN_FD", stdin_read)
    os.write(stdin_write, b"payload")

    assert clipy.justpty.forward_stdin(master_write) is True
    assert os.read(master_read, 16) == b"payload"

    os.close(stdin_write)
    assert clipy.justpty.forward_stdin(master_write) is False  # EOF

    os.close(stdin_read)
    assert clipy.justpty.forward_stdin(master_write) is False  # read error

    os.close(master_read)
    os.close(master_write)


def test_1_5_4_relay_tees_cleaned_bytes_to_the_log_and_stdout_until_the_master_fd_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    master_read, master_write = os.pipe()
    stdin_read, stdin_write = os.pipe()
    monkeypatch.setattr(clipy.justpty, "STDIN_FD", stdin_read)
    os.close(stdin_write)
    os.write(master_write, b"hello\n")
    os.close(master_write)
    log = io.StringIO()

    clipy.justpty.relay(master_read, log)

    assert log.getvalue() == "hello\n"
    os.close(master_read)
    os.close(stdin_read)


# 1.6 orchestrating a run around a stubbed child process


def test_1_6_1_copy_winsize_copies_the_real_terminal_size_when_stdout_is_a_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[tuple[int, tuple[int, int]]] = []
    monkeypatch.setattr(os, "isatty", lambda fd: fd == clipy.justpty.STDOUT_FD)
    monkeypatch.setattr(termios, "tcgetwinsize", lambda _fd: (24, 80))
    monkeypatch.setattr(termios, "tcsetwinsize", lambda fd, size: recorded.append((fd, size)))

    clipy.justpty.copy_winsize(99)

    assert recorded == [(99, (24, 80))]


def test_1_6_2_raw_stdin_is_a_no_op_when_stdin_is_not_a_tty() -> None:
    entered = False

    with clipy.justpty.raw_stdin():
        entered = True

    assert entered


def test_1_6_3_run_under_pty_wires_spawn_signals_relay_and_the_exit_code_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    master_read, master_write = os.pipe()
    os.close(master_write)
    calls: list[str] = []
    monkeypatch.setattr(clipy.justpty, "spawn_just", lambda *_args: calls.append("spawn") or (4321, master_read))
    monkeypatch.setattr(clipy.justpty, "copy_winsize", lambda _fd: calls.append("winsize"))
    monkeypatch.setattr(clipy.justpty, "forward_signals", lambda *_args: calls.append("signals"))
    monkeypatch.setattr(os, "waitpid", lambda pid, _opts: (pid, 0))
    monkeypatch.setattr(os, "waitstatus_to_exitcode", lambda _status: 0)

    exit_code = clipy.justpty.run_under_pty("just", ["recipe"], io.StringIO())

    assert exit_code == 0
    assert calls == ["spawn", "winsize", "signals"]


def test_1_6_4_link_latest_points_logs_just_log_at_the_given_run_log(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    run_log = logs_dir / "just-20260101-000000-1.log"
    run_log.write_text("x")

    clipy.justpty.link_latest(logs_dir, run_log)

    symlink = logs_dir / "just.log"
    assert symlink.is_symlink()
    assert symlink.resolve() == run_log


def test_1_6_5_run_just_writes_the_log_header_and_footer_and_prunes_stale_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(clipy.justpty, "run_under_pty", lambda *_args: FAKE_JUST_EXIT_CODE)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/just")
    monkeypatch.chdir(tmp_path)

    status = clipy.justpty.run_just(["hello"])

    assert status == FAKE_JUST_EXIT_CODE
    log_text = (tmp_path / "logs" / "just.log").read_text()
    assert "just hello" in log_text
    assert f"=== exit {FAKE_JUST_EXIT_CODE}" in log_text


def test_1_6_6_the_cli_command_exits_with_run_justs_status_code(
    cli: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(clipy.justpty, "run_just", lambda _args: FAKE_JUST_EXIT_CODE)

    result = cli.invoke(clipy.justpty.app, ["hello"])

    assert result.exit_code == FAKE_JUST_EXIT_CODE
