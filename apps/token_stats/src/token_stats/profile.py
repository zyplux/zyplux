from __future__ import annotations

import pathlib
import time
from typing import TYPE_CHECKING

import pathspec
import polars as pl
from pathspec.patterns import GitWildMatchPattern

from token_stats import ast_metrics, tokenizers
from token_stats.segment import split_code_and_docstrings

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

DEFAULT_EXCLUDE_DIRS = frozenset({
    ".venv",
    "venv",
    "node_modules",
    ".git",
    "__pycache__",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".eggs",
})

CODE_COUNTERS: list[tuple[str, Callable[[str], int]]] = [
    ("code_ast_nodes", ast_metrics.count_ast_nodes),
    ("code_native_tokens", ast_metrics.count_compiler_tokens),
    ("code_tokens_cl100k", lambda text: tokenizers.count_tiktoken_tokens("cl100k", text)),
    ("code_tokens_o200k", lambda text: tokenizers.count_tiktoken_tokens("o200k", text)),
]

DOC_COUNTERS: list[tuple[str, Callable[[str], int]]] = [
    ("doc_tokens_gpt2", lambda text: tokenizers.count_tiktoken_tokens("gpt2", text)),
    ("doc_tokens_cl100k", lambda text: tokenizers.count_tiktoken_tokens("cl100k", text)),
    ("doc_tokens_o200k", lambda text: tokenizers.count_tiktoken_tokens("o200k", text)),
]


def _timed_count(timings: dict[str, float], key: str, counter: Callable[[str], int], text: str) -> int:
    start = time.perf_counter()
    count = counter(text)
    timings[key] = timings.get(key, 0.0) + (time.perf_counter() - start)
    return count


def profile_file(file_path: pathlib.Path, timings: dict[str, float]) -> dict[str, object] | None:
    """Profile a single Python file's token counts under every tracked counter, timing each one."""
    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError:
        return None

    pure_code, docstrings = split_code_and_docstrings(source)

    metrics: dict[str, object] = {"file_path": str(file_path)}
    for key, counter in CODE_COUNTERS:
        metrics[key] = _timed_count(timings, key, counter, pure_code)
    for key, counter in DOC_COUNTERS:
        metrics[key] = _timed_count(timings, key, counter, docstrings)
    metrics["doc_chars"] = len(docstrings)
    metrics["doc_words"] = len(docstrings.split())
    return metrics


def profile_files(file_paths: Iterable[pathlib.Path], timings: dict[str, float]) -> list[dict[str, object]]:
    profiles = (profile_file(file_path, timings) for file_path in file_paths)
    return [profile for profile in profiles if profile is not None]


def _load_gitignore_spec(target: pathlib.Path) -> pathspec.PathSpec[GitWildMatchPattern] | None:
    gitignore_path = target / ".gitignore"
    if not gitignore_path.is_file():
        return None
    return pathspec.PathSpec.from_lines(GitWildMatchPattern, gitignore_path.read_text(encoding="utf-8").splitlines())


def find_python_files(target_dir: str) -> Iterable[pathlib.Path]:
    """Find Python files under a directory, respecting its .gitignore (or a default exclude list if it has none)."""
    target = pathlib.Path(target_dir)
    spec = _load_gitignore_spec(target)
    for file_path in target.rglob("*.py"):
        is_excluded = (
            spec.match_file(str(file_path.relative_to(target)))
            if spec is not None
            else not DEFAULT_EXCLUDE_DIRS.isdisjoint(file_path.parts)
        )
        if not is_excluded:
            yield file_path


def _normalize_to_100(column: str) -> pl.Expr:
    col = pl.col(column)
    span = col.max() - col.min()
    return pl.when(span == 0).then(pl.lit(0.0)).otherwise((col - col.min()) / span * 100)


def add_balance_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Add normalized (0-100) code/doc token size and their mean size rank, for ranking files by size."""
    code_cols = [name for name in df.columns if name.startswith("code_tokens_")]
    doc_cols = [name for name in df.columns if name.startswith("doc_tokens_")]
    if not code_cols or not doc_cols:
        return df
    df = df.with_columns(
        pl.mean_horizontal(code_cols).alias("code_tokens_avg"),
        pl.mean_horizontal(doc_cols).alias("doc_tokens_avg"),
    )
    df = df.with_columns(
        _normalize_to_100("code_tokens_avg").alias("code_tokens_norm"),
        _normalize_to_100("doc_tokens_avg").alias("doc_tokens_norm"),
    ).with_columns(((pl.col("code_tokens_norm") + pl.col("doc_tokens_norm")) / 2).alias("size_rank"))
    return df.with_columns(
        _normalize_to_100("doc_chars").alias("doc_chars_norm"),
        _normalize_to_100("doc_words").alias("doc_words_norm"),
    )


def scan_codebase(target_dir: str) -> tuple[pl.DataFrame, dict[str, float]]:
    """Scan a directory for Python files, collecting token profiles and per-counter timings."""
    timings: dict[str, float] = {}
    records = profile_files(find_python_files(target_dir), timings)
    return add_balance_columns(pl.DataFrame(records)), timings
