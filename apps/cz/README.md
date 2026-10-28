# @zyplux/cz

Repository helpers, exposed as the `cz` CLI: PRs, workspace maintenance, reports and file chunking. Requires [Node](https://nodejs.org) 26 and [pnpm](https://pnpm.io).

## Install

Run on demand:

```bash
pnpx @zyplux/cz <command>
```

Or install globally for the `cz` command:

```bash
pnpm add -g @zyplux/cz
cz <command>
```

## Usage

```bash
cz push-branch [-r|--ready]             Push the current branch and open or advance its draft PR.
cz clone-reference-repo <repo> [ref]    Shallow-clone a reference repo into reference_clones/.
cz deps-catalog [--dir DIR] [--out FILE] Resolve every dependency across the repos to its source repo; write catalog.json.
cz clean [--dry-run] [--exclude DIR...] Remove gitignored build artifacts/caches from this repo, or every repo under the cwd.
cz lint-mermaid                       Check Mermaid diagrams in tracked and unignored Markdown under the current Git directory.
cz upgrade [--interactive] [PACKAGE...] Upgrade the pinned toolchain plus JavaScript and Python workspace dependencies.
cz workspace-graph [PATH]              Write WORKSPACE_GRAPH.md for pnpm and uv workspaces.
cz stats [PATH] [--out FILE] [--title TITLE] Write line_and_token_stats.md through Clipy.
cz fingerprint [PATH]                  Prepare releases and both repository reports before release hashes.
cz chunk-files [FILE_LIST|-] [--json]   Balance files into word-count chunks; isolate large files.
```

## Repository reports

The workspace graph and stats use Cerberus's `source_oracle` classifications. Graph nodes combine pnpm and uv membership, group by category and exclude test workspaces. TypeScript imports distinguish type-only edges; frequently imported foundations are listed separately.

Python reporting and release orchestration live in [Clipy](../clipy/README.md). Install `zyplux-clipy` in the repository's uv workspace; CZ delegates `stats` and `fingerprint` to `uv run clipy`. Airlock owns versioning and release hashes.

Stats read tracked working-tree files, leaving the index untouched. Stage new files to include them. Lockfiles, the report itself and binary files stay outside the tables. Production tables follow the oracle; the first o200k tokenizer use may download its encoding.

`chunk-files` reads newline-delimited paths from a file or stdin (`-`). Use `--chunks N` or `--target-words N`; `--isolate-min-words N` gives large files their own chunk. Defaults are 3,500 target words and a 2,500-word isolation threshold.

## License

MIT
