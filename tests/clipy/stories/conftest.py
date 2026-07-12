"""Fixtures for the clipy story tests; the only external boundaries — the real `just` binary justpty
wraps, and the VS Code process tree / extension-host websocket ctop inspects — are faked or bypassed by
exercising the pure labeling/rendering functions directly."""

from __future__ import annotations

import os
import signal
import stat
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

RESTORED_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGWINCH)


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _restore_signal_handlers() -> Generator[None]:
    """justpty installs real SIGINT/SIGTERM/SIGHUP/SIGWINCH handlers around each PTY run; restore pytest's own."""
    saved = {sig: signal.getsignal(sig) for sig in RESTORED_SIGNALS}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


@pytest.fixture
def fake_just(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], Path]:
    """Installs a scripted `just` on PATH (ahead of the real one) and chdirs into a fresh working directory."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.chdir(tmp_path)

    def install(script_body: str) -> Path:
        just_path = bin_dir / "just"
        just_path.write_text(f"#!/usr/bin/env bash\n{script_body}\n")
        just_path.chmod(just_path.stat().st_mode | stat.S_IEXEC)
        return just_path

    return install
