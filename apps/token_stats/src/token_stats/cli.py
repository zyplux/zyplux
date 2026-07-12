from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from token_stats.profile import CODE_COUNTERS, DOC_COUNTERS, scan_codebase

if TYPE_CHECKING:
    import polars as pl

app = typer.Typer(add_completion=False)
console = Console(highlight=False)

LARGEST_FILES_LIMIT = 10

CODE_COUNTER_COLUMNS = [key for key, _ in CODE_COUNTERS] + ["code_tokens_norm"]
DOC_COUNTER_COLUMNS = [key for key, _ in DOC_COUNTERS] + ["doc_tokens_norm", "doc_chars_norm", "doc_words_norm"]

NOT_SUMMABLE_COLUMNS = frozenset({
    "code_tokens_avg",
    "doc_tokens_avg",
    "code_tokens_norm",
    "doc_tokens_norm",
    "size_rank",
})


def _print_totals(df: pl.DataFrame, timings: dict[str, float]) -> None:
    totals = df.drop("file_path").sum()
    columns = [column for column in totals.columns if column not in NOT_SUMMABLE_COLUMNS]
    columns.sort(key=lambda column: timings.get(column, -1.0), reverse=True)

    table = Table(title=f"Totals ({df.height} files)")
    table.add_column("metric")
    table.add_column("value", justify="right")
    table.add_column("seconds", justify="right")
    for column in columns:
        seconds = timings.get(column)
        table.add_row(column, f"{totals[column].item():.0f}", f"{seconds:.3f}" if seconds is not None else "-")
    console.print(table)


def _format_metric(value: float, column: str) -> str:
    return f"{value:.1f}" if column.endswith("_norm") else f"{value:.0f}"


def _short_column_name(column: str, prefix: str) -> str:
    return column.removeprefix(prefix).removeprefix("tokens_").removesuffix("_tokens")


def _print_largest_files_table(largest: pl.DataFrame, title: str, prefix: str, columns: list[str]) -> None:
    table = Table(title=title)
    table.add_column("file_path")
    for column in columns:
        table.add_column(_short_column_name(column, prefix), justify="right")
    for row in largest.iter_rows(named=True):
        table.add_row(row["file_path"], *(_format_metric(row[column], column) for column in columns))
    console.print(table)


def _print_correlation_matrix(df: pl.DataFrame, title: str, prefix: str, columns: list[str]) -> None:
    short_names = [_short_column_name(column, prefix) for column in columns]
    corr = df.select(columns).corr()

    table = Table(title=title)
    table.add_column("metric")
    for name in short_names:
        table.add_column(name, justify="right")
    for name, row in zip(short_names, corr.iter_rows(), strict=True):
        table.add_row(name, *(f"{value:.4g}" for value in row))
    console.print(table)


def _print_largest_files(df: pl.DataFrame) -> None:
    if "size_rank" not in df.columns:
        return

    largest = df.sort("size_rank", descending=True).head(LARGEST_FILES_LIMIT)
    _print_largest_files_table(largest, "Largest Files (Code)", "code_", CODE_COUNTER_COLUMNS)
    _print_correlation_matrix(df, "Code Counter Correlations", "code_", CODE_COUNTER_COLUMNS)
    _print_largest_files_table(largest, "Largest Files (Doc)", "doc_", DOC_COUNTER_COLUMNS)
    _print_correlation_matrix(df, "Doc Counter Correlations", "doc_", DOC_COUNTER_COLUMNS)


@app.command()
def main(
    target_dir: str = typer.Argument(".", help="directory to scan"),
    out_path: str = typer.Option("out/codebase_token_profile.parquet", help="path to write the Parquet report to"),
) -> None:
    """Profile token counts across a Python codebase."""
    df, timings = scan_codebase(target_dir)

    _print_totals(df, timings)
    _print_largest_files(df)

    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_path)
    console.print(f"\nMetrics exported to '{out_path}'")


if __name__ == "__main__":
    app()
