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
| `justfile`              | content     | Recipe names, aliases, `check` pipeline, wrapped tool calls, no trailing whitespace |
| `ci-workflow`           | content     | `ci.yml` exists, exposes a `ci` check, runs on PRs (push to `main` recommended)      |
| `ci-sequence`           | content     | `ci.yml` runs the canonical check sequence per stack, in the org container          |
| `cerberus-step`         | content     | A CI workflow runs cerberus to self-verify org invariants                           |
| `workflow-tooling`      | content     | Workflows set up only the workspace toolchain (uv, bun), not extra tools            |
| `rumdl-config`          | content     | `.rumdl.toml` carries the org-canonical rule config (per-repo `exclude` allowed)    |
| `vitest-runner`         | content     | TypeScript tests run on vitest, never bun's built-in test runner                    |
| `ts-project-references` | content     | TypeScript typecheck runs via project references (`tsc -b`), not a per-package fan-out |
| `catalog-discipline`    | content     | Every workspace `package.json` dependency pins via `catalog:` or `workspace:`        |
| `release-bumps`         | git-history | A published target's version is bumped whenever its release surface changes          |
| `codeowners`            | content     | `CODEOWNERS` present and covers `/.github/`                                          |

## Config

Policy — required recipes and aliases, the canonical CI sequence — lives in [`cerberus.toml`](src/cerberus/cerberus.toml). Override it with `--config PATH`.
