# <img src="docs/assets/logo.svg" alt="" width="24"> zyplux

<div align="center">

<img src="docs/assets/og.png" alt="Zyplux — Neural Intelligence Systems" width="640">

**The [Zyplux](https://zyplux.ai) platform monorepo** — one source of truth for the org's shared tooling and standards, published to npm, PyPI, and GHCR and consumed by every product repo.

</div>

## Published packages

| Package                                          | Registry | What it is                                                                       |
| ------------------------------------------------ | -------- | -------------------------------------------------------------------------------- |
| [zyplux-cerberus](apps/cerberus)                 | PyPI     | 🐺 Org-invariant linter: CI workflows, justfiles, CODEOWNERS, coverage, releases |
| [@zyplux/cz](apps/cz)                            | npm      | Repo automation CLI: releases, PR flow, parallel tests, cleanup                  |
| [totchef](apps/totchef)                          | PyPI     | 🧑‍🍳 Declarative machine setup: write a recipe, run one command                    |
| [@zyplux/eslint-config](packages/eslint-config)  | npm      | Shared ESLint flat config and custom rules                                       |
| [@zyplux/tsconfig](packages/tsconfig)            | npm      | Shared TypeScript presets                                                        |
| [@zyplux/util](packages/util-ts)                 | npm      | Bun utilities: assertions, polling, zod-validated parsing, git/gh shell harness  |
| [zyplux-util](packages/util_py)                  | PyPI     | Python counterpart of the shared utilities                                       |
| [@zyplux/tests-fixtures](tests/fixtures)         | npm      | Test doubles (shell fake, CLI runner) for story tests                            |
| [ghcr.io/zyplux/ci](containers/ci)               | GHCR     | CI image the org's workflows run on                                              |

Each package's README covers usage. Releases are cut per package from [release-targets.toml](release-targets.toml) via `cz release-bumped-targets`.

## Develop

Dual workspace: bun (TS) + uv (Python), orchestrated by [just](https://github.com/casey/just).

```sh
just install   # both workspaces
just check     # full gate: install, knip, typecheck, lint, test, cerberus
```

Run `just` for the full recipe list. This repo is the org's quality reference — it dogfoods every new strict check first (see [cerberus.toml](cerberus.toml)), and `just check` must pass clean.
