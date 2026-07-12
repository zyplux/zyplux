"""Story: scanning a codebase for token stats produces a Parquet report, one row per Python file."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from pathlib import Path


def test_1_1_1_writes_a_parquet_report_with_one_row_per_python_file(codebase: Path, scanned_rows: pl.DataFrame) -> None:
    assert set(scanned_rows["file_path"]) == {
        str(codebase / "module_a.py"),
        str(codebase / "module_b.py"),
        str(codebase / "unicode_docstring.py"),
    }


def test_1_1_2_skips_non_python_files(scanned_rows: pl.DataFrame) -> None:
    assert all(path.endswith(".py") for path in scanned_rows["file_path"])


def test_1_1_3_skips_python_files_under_vendored_dependency_directories(scanned_rows: pl.DataFrame) -> None:
    assert not any(".venv" in path for path in scanned_rows["file_path"])


def test_1_1_4_counts_ast_nodes_for_files_with_multibyte_unicode_in_a_docstring(
    codebase: Path, scanned_rows: pl.DataFrame
) -> None:
    row = scanned_rows.filter(pl.col("file_path") == str(codebase / "unicode_docstring.py")).row(0, named=True)
    assert row["code_ast_nodes"] > 0
