"""Fixtures for the token-stats story tests; the only external boundary — tiktoken tokenizer
downloads — is mocked, everything else (file scanning, Parquet writing) runs for real."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl
import pytest
import token_stats.tokenizers
from token_stats.cli import app
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _fake_tokenizer_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(token_stats.tokenizers, "count_tiktoken_tokens", lambda _encoding_key, text: len(text.split()))


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


@pytest.fixture
def codebase(tmp_path: Path) -> Path:
    (tmp_path / "module_a.py").write_text(
        '"""Module docstring."""\n\n\ndef greet() -> str:\n    """Say hi."""\n    return "hi"\n'
    )
    (tmp_path / "module_b.py").write_text("x = 1\n")
    (tmp_path / "notes.txt").write_text("not python\n")
    vendored_dir = tmp_path / ".venv" / "lib" / "site-packages"
    vendored_dir.mkdir(parents=True)
    (vendored_dir / "vendored.py").write_text("y = 2\n")
    (tmp_path / "unicode_docstring.py").write_text(
        'def f():\n    """before == current ≠ latest — done."""\n    return 1\n'
    )
    return tmp_path


@pytest.fixture
def scanned_rows(cli: CliRunner, codebase: Path, tmp_path: Path) -> pl.DataFrame:
    out_path = tmp_path / "report.parquet"
    result = cli.invoke(app, [str(codebase), "--out-path", str(out_path)])
    assert result.exit_code == 0
    return pl.read_parquet(out_path)
