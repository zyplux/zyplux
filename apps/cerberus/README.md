# cerberus

Verifies repository invariants — CI workflow structure, justfile and dependency conventions, CODEOWNERS, and release-version bumps — as a per-repo linter against a checkout.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) and Python 3.14

The `justfile_baseline` bite shells out to `just`, which ships with the package (via [`rust-just`](https://pypi.org/project/rust-just/)) — no separate install.

## Lint a repo

```sh
uv run cerberus            # lint the current directory
uv run cerberus PATH       # lint a checkout at PATH
```

Runs every bite and exits non-zero on any failure or error, so it drops into CI like any linter. Run `cerberus list` to see every bite, its scope, and what it verifies.

| Option          | Description                                          |
| --------------- | ---------------------------------------------------- |
| `--check NAME`  | Limit to named bite(s); repeatable                   |
| `--config PATH` | Use a `cerberus.toml` other than the bundled         |
| `--fix`         | Auto-fix fixable problems (e.g. trailing whitespace) |

A repo opts out of specific bites with `[tool.cerberus] disable = ["bite_id", ...]` in its `pyproject.toml`.

## Bites

| ID                             | Scope       | Verifies                                                                            |
| ------------------------------ | ----------- | ----------------------------------------------------------------------------------- |
| `justfile_baseline`            | content     | Canonical baseline block (byte-exact, `--fix`able), recipe names, aliases, `check` pipeline, local cerberus run, wrapped tool calls, no trailing whitespace |
| `zyplux_deps_latest`           | content     | Every `@zyplux/*` npm package, `zyplux-*` PyPI distribution, and `ghcr.io/zyplux` image is used at its latest release |
| `ci_workflow_gate`             | content     | `ci.yml` exists, exposes a `ci` check, runs on PRs (push to `main` recommended)      |
| `ci_check_sequence`            | content     | `ci.yml` runs the canonical check sequence per stack, in the org container          |
| `ci_cerberus_step`             | content     | A CI workflow runs cerberus to self-verify org invariants                           |
| `workflow_toolchain_only`      | content     | Workflows set up only the workspace toolchain (uv, bun), not extra tools            |
| `pyrefly_strict`               | content     | All code, tests included, type-checks under strict pyrefly with no relaxations       |
| `ruff_select_all`              | content     | ruff runs standalone in preview with `select = ["ALL"]`; relaxations stay sanctioned |
| `line_length_120`              | content     | ruff `line-length` and prettier `printWidth` are both 120                            |
| `rumdl_canonical_config`       | content     | `.rumdl.toml` carries the org-canonical rule config (per-repo `exclude` allowed)    |
| `knip_standalone_config`       | content     | knip config is standalone, never inline in `package.json`; `knip.prod.json` runs the entry-exports pass and exempts exactly the repo's published npm targets |
| `vitest_only_runner`           | content     | TypeScript tests run on vitest, never bun's built-in test runner (package.json, justfile, CI) |
| `tsc_project_references`       | content     | TypeScript typecheck runs via project references (`tsc -b`), not a per-package fan-out |
| `catalog_pinned_deps`          | content     | Every workspace `package.json` dependency pins via `catalog:` or `workspace:`        |
| `story_tests_lockstep_py`      | content     | `tests/**/stories/*.md` criteria have a matching, title-matched pytest test          |
| `story_tests_lockstep_ts`      | content     | `tests/**/stories/*.md` criteria have a matching, title-matched vitest test          |
| `cli_ts_test_seam`             | content     | CLI apps export only the root seam; story tests reach workspace code via fixture aliases |
| `lib_ts_test_seam`             | content     | Libraries export only the root seam; story tests reach workspace code via fixture aliases |
| `cli_py_test_seam`             | content     | CLI apps' story tests import only their root module or cli entry module              |
| `lib_py_test_seam`             | content     | Libraries' story tests import only their root module                                |
| `release_surface_version_bump` | git-history | A published target's version is bumped whenever its release surface changes          |
| `codeowners_coverage`          | content     | `CODEOWNERS` present and covers `/.github/`                                          |
| `pytest_coverage_floor`        | content     | `pyproject.toml` `[tool.coverage.report] fail_under` is set to at least 90%          |
| `vitest_coverage_floor`        | content     | The root `vitest.config.*` `coverage.thresholds` are all set to at least 90%         |
| `jscpd_dupes_threshold`        | content     | Copy-paste duplication per language stays under the configured jscpd threshold      |
| `fallow_analyzer`              | content     | fallow finds no unused code, circular imports, or functions above its complexity thresholds |

## The justfile baseline

Every repo's `justfile` must start with the line `# BASELINE`, carry the canonical block from [`baseline.just`](src/cerberus/baseline.just) byte-for-byte, and close it with a `# CUSTOM` line. Everything after `# CUSTOM` is the repo's own (extra aliases, recipes, `set`/`mod` statements, variables). With both markers present, `--fix` restores a drifted baseline region and leaves the custom tail untouched; the zyplux repo's own `justfile` mirrors the packaged canonical, and cerberus keeps the two identical.

## Config

Policy — required recipes and aliases, the canonical CI sequence — lives in [`cerberus.toml`](src/cerberus/cerberus.toml). Override it with `--config PATH`.

`zyplux_deps_latest` queries npm, PyPI, and GHCR at lint time; a failed lookup is reported as an error, never a silent pass. It has no `--fix` — run `just upgrade` to catch up.
