---
name: cerberus-graph
description: >
  Build, explain, and query a dependency graph of a repo's own Python and
  TypeScript source via `cerberus graph` / `graph-explain` / `graph-query` —
  pure tree-sitter AST + import resolution, no LLM calls, no network. Use
  when asked how two files or symbols connect, what something's neighbors
  are, or to get a quick structural map of an unfamiliar part of a repo that
  has cerberus installed (not limited to this one). Rebuild whenever source
  has changed since the last `cerberus graph` run — nothing watches for you.
metadata:
  kind: prompt
  version: "0.1.0"
  user-invocable: "true"
  argument-hint: "[explain <node> | query <question> | (no args to build/rebuild)]"
---

# cerberus-graph

Three commands, one `graph.json` (default: repo root). Works in any repo with
`cerberus` on PATH — not specific to this checkout.

## 1. Build

```bash
cerberus graph [path] [--out DIR]
```

`path` defaults to cwd, `graph.json` is written there unless `--out` says
otherwise. Deterministic: tree-sitter AST for `.py`/`.ts`/`.tsx`, import
resolution (relative, absolute, TS workspace-alias via `package.json`
exports), top-level function/class symbols. No semantic/LLM pass — rebuild
is cheap and safe to run as often as needed, but it is **not** incremental
and does **not** watch — re-run it yourself after source changes before
trusting `graph-explain`/`graph-query` again.

## 2. Explain one node

```bash
cerberus graph-explain "<node>" [--graph PATH]
```

`<node>` can be an exact node id (`apps_cerberus_src_cerberus_context`), or a
source path/label (`apps/cerberus/src/cerberus/context.py`, `Context`,
`top_level_func`) — matched by substring/token score when it isn't an exact
id. Prints the node's id, source location, community, degree, and every
neighbor with its relation (`imports`/`contains`) and confidence.

Use this when you already know *which* file or symbol you care about and
want its direct connections without grepping for every import site by hand.

## 3. Query with free text

```bash
cerberus graph-query "<question>" [--depth N] [--dfs] [--budget N] [--graph PATH]
```

Seeds a BFS (default, `--dfs` for depth-first) traversal from the best
free-text matches for `<question>`, depth-limited (`--depth`, default 2),
and renders budget-truncated text (`--budget`, a character count, default
2000). Seeding is a plain substring/token score — no IDF weighting, no
trigram index — good enough for a one-shot CLI call, but an ambiguous
multi-word question may seed more (or fewer) starting nodes than you expect;
narrow the wording or pass an exact node id as `<node>`/seed text if so.

Use this for broader "what's connected around X" questions where you don't
already know the exact node to `graph-explain`.

## Efficient use

- Build once per session per repo, not per question — reuse the same
  `graph.json` across several `graph-explain`/`graph-query` calls.
- Prefer `graph-explain` when you know the file/symbol; reach for
  `graph-query` only when you need to discover what's nearby.
- `graph-explain`/`graph-query` both fail fast with a clear error if
  `graph.json` doesn't exist yet at the expected path — build first.
- Node ids: a file's id is its repo-relative path with the extension
  stripped and non-word characters folded to `_` (`packages/util/src/index.ts`
  → `packages_util_src_index`); a symbol's id is `<owning-file-id>__<slug>`.
  You rarely need to construct these by hand — pass the path or name instead
  and let the matcher resolve it.
