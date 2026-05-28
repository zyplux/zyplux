# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`totchef` — an idempotent, declarative system configurator for Ubuntu/Kubuntu, published as a `uv` tool. You write a `recipe.toml`; the `totchef` command makes the system comply. Serves both first-run bootstrap and ongoing upkeep — re-runs only touch what would actually change. The repo's own machine config (a hybrid-GPU laptop: apt repos/packages, vendor CLIs, eGPU auto-PRIME, per-app GPU flags) lives as a worked example in `examples/recipe.toml`.

The package is `src/totchef/`; `pyproject.toml` exposes the `totchef` console script (`totchef.cli:main`) and registers the built-in cooks under the `totchef.cooks` entry-point group.

## Commands

Tooling is `uv` (Python ≥ 3.14) driven through `just`. The dev `just` targets run `uv run totchef <cmd> --recipe examples/recipe.toml`:

- `just up` — apply the example recipe (re-execs under sudo).
- `just plan` — dry-run: probe and print the report, no changes, no root.
- `just lint` — `ruff check --fix` + `ruff format` + `rumdl` + `totchef lint` (validate the recipe against cook schemas).
- `just tc` — lint, then `uvx pyright`.
- `just test` — typecheck, then `uv run pytest`.
- `just cooks` — list every resolvable cook (built-in / plugin / local) via `totchef --list-cooks`.
- Single test: `uv run pytest tests/test_recipe_graph.py::test_name`.
- `just clone <owner/name|url> [ref]` — shallow-clone a reference repo into `reference_clones/` for browsing; with a `ref`, keep history back to (but excluding) that commit. Not part of `up`/idempotency — a manual dev helper.

The CLI is subcommand-based (`totchef up|plan|lint|where`, plus `--version` and `--list-cooks` flags), with a global `--recipe/-r PATH`.

## Architecture

The core abstraction is **chef** (the orchestrator, `cli.py`) driving **cooks** (thin per-domain managers). Chef owns every diff/idempotency decision; a cook only *probes* current state and *acts* — it holds no diff logic.

Flow (`src/totchef/cli.py`): `recipe.find_recipe` resolves the recipe path → re-exec as root (pinning the resolved path via `$TOTCHEF_RECIPE`) → parse → `schema_lint.validate` → `recipe_graph` builds a DAG → `cook_runner.run_recipe` topo-sorts and runs it → report. Exit codes: `0` ok, `75` soft fail, `1` hard fail (aborts).

**Recipe discovery** (`src/totchef/recipe.py`): `--recipe`/`$TOTCHEF_RECIPE` → walk up from cwd → `~/.config/totchef/recipe.toml` → `/etc/totchef/recipe.toml`. Resolved once as the invoking user (before sudo re-exec) and passed through so root cooks see the same file.

**Section → cook via the registry** (`src/totchef/registry.py`). A section `[foo]` resolves to whatever cook registered the name `foo`: built-in and third-party cooks both declare it in the `totchef.cooks` entry-point group, and a loose `~/.config/totchef/cooks/foo_cook.py` (one `CookBase` subclass; `_cook`/`_root_cook` suffix stripped to get the section) is an escape hatch that shadows them. A cook's `needs_root` class attribute, not its filename, decides privilege. Adding a built-in domain = add `[project.entry-points."totchef.cooks"]` `foo = "totchef.cooks.foo_cook:FooCook"` in `pyproject.toml` + the cook class with its `entry_model`.

**The recipe is the single source of config.** The two chef-reserved per-entry fields are `needs_root` and `depends_on` (stripped before the slice reaches the cook). A subtable section (`[url.<name>]`) fans out to one graph node per entry; a plain-data section (`[apt_pkg]`) is one node. The section/field rules are documented for users in the README, not in the recipe itself.

**Two cook shapes** (`src/totchef/cook_base.py`):

- `VersionedCook` — versioned packages. Implements `list_requested` / `list_installed` / `find_latest` / `sync`. `PackageListCook` covers plain `packages = [...]` sections (cargo, uv, snap, apt_pkg).
- `StateCook` — desired-state resources. Implements `get_current_state` / `get_desired_state` / `apply_resource`, plus `get_hooks`. `FileStateCook` diffs by sha256 of rendered bytes vs on-disk file.

`EntrySpec` (pydantic, `extra='forbid'`) is each cook's recipe-entry schema, so a typo'd key fails the run instead of being silently ignored. `pre_hook` (guard: non-zero skips the item) and `post_hook` (runs after a change) live on `StateEntrySpec`, the base for state-cook entries — only `StateCook` honors them, so a versioned section keeps the bare `EntrySpec` and a hook declared there fails the lint instead of silently never running. Cooks compose intrinsic hooks via `chain_hooks`.

**Convergence is create/update only.** Cooks drive resources toward their desired *presence*; they never prune. Removing an entry from the recipe (or uninstalling its target) leaves prior artifacts in place — a stale `.desktop` override, a repo's keyring + `.sources`, a written `/etc` drop-in. Teardown is manual (see the README).

**Privilege model** (`src/totchef/harness.py`, `cook_runner`): chef runs as root. Every node runs in a **forked child** that pipes its `CookResult` back as pickle — a `needs_root` child keeps root, every other child calls `become_user()` (drops gid→groups→uid, repoints `HOME`/`USER`/`PATH` at the invoking `SUDO_USER`). User nodes run with unbounded concurrency; root nodes are serialized to one at a time (they share the dpkg lock and write the same `/etc`), so a long root cook never blocks an independent user node from starting once its own `depends_on` clears. `totchef lint` rejects `needs_root` on a subtable header — grant it per leaf entry (least privilege). Forking only happens from the main thread to keep loguru's locks safe.

**Logging** (`src/totchef/logs.py`): one parent thread (the "pump") owns the log file and terminal — fd 1/2 of the parent and every forked cook funnel through a single pipe, so a live rich region (table/progress in `terminal.py`) never interleaves with log lines. Logs are timestamped per run under the invoking user's XDG state dir (`~/.local/state/totchef/logs/`), resolved from `SUDO_USER` so a root re-exec still writes to the user's home, then chowned back to them.

## Static assets

`src/totchef/files/` holds files installed verbatim (the `egpu-prime` switch + its systemd unit, and `write-if-changed`), bundled into the wheel and referenced by `[file.<name>]` entries via `source`.
