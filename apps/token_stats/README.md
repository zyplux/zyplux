# token-stats

Profiles a Python codebase's token counts under several tokenizers side by side — native compiler tokens, AST node counts, and three tiktoken encodings (`cl100k`, `o200k`, `gpt2`) — so the numbers, and how long each counter takes, can be compared.

## Usage

```bash
uv run token-stats [TARGET_DIR] [--out-path PATH]
```

Defaults to scanning the current directory and writing `out/codebase_token_profile.parquet` (the `out` directory is created if missing). Prints a Totals table (sums per counter alongside its timing, sorted slowest first), the top 10 largest files split into Code and Doc column sets, and a correlation matrix for each set showing how its counters track each other across the whole scan. Largest files are ranked by the mean of each file's code and doc token counts independently normalized to 0-100 across the scan, so a file doesn't need to lead on both axes to rank highly. The Parquet report keeps every per-file metric, including the normalized `code_tokens_norm`/`doc_tokens_norm`/`size_rank` columns, for further analysis (e.g. in a notebook via `pl.read_parquet`).

Skips whatever the target directory's `.gitignore` excludes (e.g. `.venv`, `node_modules`), or a default vendor/build exclude list if it has none.
