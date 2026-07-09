# cerberus

Verifies repository invariants — CI workflow structure, justfile and dependency conventions, CODEOWNERS, and release-version bumps — as a per-repo linter against a checkout.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) and Python 3.14

The `justfile` bite shells out to `just`, which ships with the package (via [`rust-just`](https://pypi.org/project/rust-just/)) — no separate install. The `jscpd` and `fallow` bites run their tools via `bunx` at exact versions pinned in [`tool_pins.py`](src/cerberus/tool_pins.py), so every cerberus release measures with the same tools everywhere; `bunx` (bun) must be on PATH.

## Lint a repo

```sh
uv run cerberus            # lint the current directory
uv run cerberus PATH       # lint a checkout at PATH
```

Runs every bite and exits non-zero on any failure or error, so it drops into CI like any linter. Run `cerberus list` to see every bite, its scope, and what it verifies.

| Option           | Description                                                       |
| ---------------- | ----------------------------------------------------------------- |
| `--check NAME`   | Limit to named bite(s); repeatable                                |
| `--config PATH`  | Overlay file applied in place of the repo root `cerberus.toml`    |
| `--fix`          | Auto-fix fixable problems (e.g. trailing whitespace)              |
| `--verbose`/`-v` | Itemize what each bite measured (clones, dead-code issues)        |

A repo switches a bite off with `off = true` in that bite's `cerberus.toml` table (see Config below); naming an off bite with `--check` still runs it.

## Bites

| ID                             | Scope       | Verifies                                                                            |
| ------------------------------ | ----------- | ----------------------------------------------------------------------------------- |
| `justfile`                     | content     | Canonical baseline block (byte-exact, `--fix`able), recipe names, aliases, `check` pipeline, local cerberus run, wrapped tool calls, no trailing whitespace |
| `ci_workflow_gate`             | content     | `ci.yml` exists, exposes a `ci` check, runs on PRs (push to `main` recommended)      |
| `ci_check_sequence`            | content     | `ci.yml` runs the canonical check sequence per stack, in the org container          |
| `ci_cerberus_step`             | content     | A CI workflow runs cerberus to self-verify org invariants                           |
| `workflow_toolchain_only`      | content     | Workflows set up only the workspace toolchain (uv, bun), not extra tools            |
| `pyrefly`                      | content     | All code, tests included, type-checks under strict pyrefly with no relaxations       |
| `ruff`                         | content     | ruff runs standalone in preview with `select = ["ALL"]`; relaxations stay sanctioned |
| `line_length`                  | content     | ruff `line-length` and prettier `printWidth` both match the configured width (120)   |
| `rumdl`                        | content     | `.rumdl.toml` carries the org-canonical rule config (per-repo `exclude` allowed)    |
| `knip`                         | content     | knip config is standalone, never inline in `package.json`; `knip.prod.json` runs the entry-exports pass and exempts exactly the repo's published npm targets |
| `vitest`                       | content     | TypeScript tests run on vitest, never bun's runner (package.json, justfile, CI), and the root `vitest.config.*` `coverage.thresholds` meet the floor (90%) |
| `tsc`                          | content     | TypeScript typecheck runs via project references (`tsc -b`), not a per-package fan-out |
| `catalog_pinned_deps`          | content     | Every workspace `package.json` dependency pins via `catalog:` or `workspace:`        |
| `story_tests_lockstep_py`      | content     | `tests/**/stories/*.md` criteria have a matching, title-matched pytest test          |
| `story_tests_lockstep_ts`      | content     | `tests/**/stories/*.md` criteria have a matching, title-matched vitest test          |
| `cli_ts_test_seam`             | content     | CLI apps export only the root seam; story tests reach workspace code via fixture aliases |
| `lib_ts_test_seam`             | content     | Libraries export only the root seam; story tests reach workspace code via fixture aliases |
| `cli_py_test_seam`             | content     | CLI apps' story tests import only their root module or cli entry module              |
| `lib_py_test_seam`             | content     | Libraries' story tests import only their root module                                |
| `release_surface_version_bump` | git-history | A published target's version is bumped whenever its release surface changes          |
| `codeowners_coverage`          | content     | `CODEOWNERS` present and covers `/.github/`                                          |
| `pytest`                       | content     | `pyproject.toml` `[tool.coverage.report] fail_under` meets the floor (90%)           |
| `jscpd`                        | content     | Copy-paste duplication per language stays under the configured jscpd threshold      |
| `fallow`                       | content     | fallow finds no unused code, circular imports, or functions above its complexity thresholds |
| `zyplux_deps_latest`           | content     | Every `@zyplux/*` npm package, `zyplux-*` PyPI distribution, and `ghcr.io/zyplux` image is used at its latest release |
| `tool_pins_latest`             | content     | The npm tool versions pinned in cerberus source are the latest npm releases (skips repos not carrying the pin source) |

## The justfile baseline

Every repo's `justfile` must start with the line `# BASELINE`, carry the canonical block from [`baseline.just`](src/cerberus/baseline.just) byte-for-byte, and close it with a `# CUSTOM` line. Everything after `# CUSTOM` is the repo's own (extra aliases, recipes, `set`/`mod` statements, variables). With both markers present, `--fix` restores a drifted baseline region and leaves the custom tail untouched; the zyplux repo's own `justfile` mirrors the packaged canonical, and cerberus keeps the two identical.

## Config

Every bite default — required recipes and aliases, the canonical CI sequence, coverage floors, line width, sanctioned lint relaxations, the canonical rumdl config — lives in [`cerberus.toml`](src/cerberus/cerberus.toml), each setting under its bite's table (`[justfile]`, `[pytest]`, `[jscpd]`, …). That bundled file is part of the code: it is the single home of the defaults, the loader treats a missing key as an error rather than falling back to a value hidden in source, and every bite has a table — bites with nothing to configure carry an empty one, so the file doubles as the visible index of everything cerberus checks. A repo adjusts the defaults by shipping a `cerberus.toml` at its root: it overlays the bundled configuration key by key, so it only names what it overrides (e.g. a stricter `[jscpd] threshold`). An explicit `--config PATH` overlays the same way, standing in for the repo's own file.

Every bite table also takes a common `off` key, handled by the runner: `off = true` removes the bite from the run entirely — no output line — and an overlay's `off = false` re-enables a bite the bundled defaults ship off. `tool_pins_latest` ships off for exactly that reason: only the repo carrying the pin source can act on it, and that repo's overlay switches it on.

`zyplux_deps_latest` queries npm, PyPI, and GHCR at lint time; a failed lookup is reported as an error, never a silent pass. It has no `--fix` — run `just upgrade` to catch up.

`tool_pins_latest` guards the jscpd/fallow pins the same way, but runs only in the repo that carries `tool_pins.py` — the one place a pin can be bumped. Consumer repos never see it (bundled `off = true`) and pick new pins up with the next cerberus release, which `zyplux_deps_latest` already forces them onto.
