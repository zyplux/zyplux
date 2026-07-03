# cerberus

Verifies repository invariants — CI workflow structure, justfile and dependency conventions, CODEOWNERS, and release-version bumps — as a per-repo linter against a checkout.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) and Python 3.14

The `justfile` check shells out to `just`, which ships with the package (via [`rust-just`](https://pypi.org/project/rust-just/)) — no separate install.

## Lint a repo

```sh
uv run cerberus            # lint the current directory
uv run cerberus PATH       # lint a checkout at PATH
```

Runs every check and exits non-zero on any failure or error, so it drops into CI like any linter. Run `cerberus list` to see every check, its scope, and what it verifies.

| Option          | Description                                          |
| --------------- | ---------------------------------------------------- |
| `--check NAME`  | Limit to named check(s); repeatable                  |
| `--config PATH` | Use a `cerberus.toml` other than the bundled         |
| `--fix`         | Auto-fix fixable problems (e.g. trailing whitespace) |

A repo opts out of specific checks with `[tool.cerberus] disable = ["check-id", ...]` in its `pyproject.toml`.

## Checks

| ID                      | Scope       | Verifies                                                                            |
| ----------------------- | ----------- | ----------------------------------------------------------------------------------- |
| `justfile`              | content     | Canonical baseline block (byte-exact, `--fix`able), recipe names, aliases, `check` pipeline, local cerberus run, wrapped tool calls, no trailing whitespace |
| `zyplux-latest`         | content     | Every `@zyplux/*` npm package, `zyplux-*` PyPI distribution, and `ghcr.io/zyplux` image is used at its latest release |
| `ci-workflow`           | content     | `ci.yml` exists, exposes a `ci` check, runs on PRs (push to `main` recommended)      |
| `ci-sequence`           | content     | `ci.yml` runs the canonical check sequence per stack, in the org container          |
| `cerberus-step`         | content     | A CI workflow runs cerberus to self-verify org invariants                           |
| `workflow-tooling`      | content     | Workflows set up only the workspace toolchain (uv, bun), not extra tools            |
| `pyrefly-config`        | content     | All code, tests included, type-checks under strict pyrefly with no relaxations       |
| `ruff-config`           | content     | ruff runs standalone in preview with `select = ["ALL"]`; relaxations stay sanctioned |
| `line-length`           | content     | ruff `line-length` and prettier `printWidth` are both 120                            |
| `rumdl-config`          | content     | `.rumdl.toml` carries the org-canonical rule config (per-repo `exclude` allowed)    |
| `vitest-runner`         | content     | TypeScript tests run on vitest, never bun's built-in test runner (package.json, justfile, CI) |
| `ts-project-references` | content     | TypeScript typecheck runs via project references (`tsc -b`), not a per-package fan-out |
| `catalog-discipline`    | content     | Every workspace `package.json` dependency pins via `catalog:` or `workspace:`        |
| `story-tests-py`        | content     | `tests/**/stories/*.md` criteria have a matching, title-matched pytest test          |
| `story-tests-ts`        | content     | `tests/**/stories/*.md` criteria have a matching, title-matched vitest test          |
| `cli-ts-tests`         | content     | CLI apps export only the root seam; story tests reach workspace code via fixture aliases |
| `lib-ts-tests`         | content     | Libraries export only the root seam; story tests reach workspace code via fixture aliases |
| `release-bumps`         | git-history | A published target's version is bumped whenever its release surface changes          |
| `codeowners`            | content     | `CODEOWNERS` present and covers `/.github/`                                          |
| `pytest-coverage`       | content     | `pyproject.toml` `[tool.coverage.report] fail_under` is set to at least 90%          |
| `vitest-coverage`       | content     | The root `vitest.config.*` `coverage.thresholds` are all set to at least 90%         |

## The justfile baseline

Every repo's `justfile` must start with the line `# BASELINE`, carry the canonical block from [`baseline.just`](src/cerberus/baseline.just) byte-for-byte, and close it with a `# CUSTOM` line. Everything after `# CUSTOM` is the repo's own (extra aliases, recipes, `set`/`mod` statements, variables). With both markers present, `--fix` restores a drifted baseline region and leaves the custom tail untouched; the zyplux repo's own `justfile` mirrors the packaged canonical, and cerberus keeps the two identical.

## Config

Policy — required recipes and aliases, the canonical CI sequence — lives in [`cerberus.toml`](src/cerberus/cerberus.toml). Override it with `--config PATH`.

`zyplux-latest` queries npm, PyPI, and GHCR at lint time; a failed lookup is reported as an error, never a silent pass. It has no `--fix` — run `just upgrade` to catch up.
