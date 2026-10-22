# <img src="docs/assets/logo.svg" alt="" width="24"> zyplux

<div align="center">

<img src="docs/assets/og.png" alt="Zyplux — Neural Intelligence Systems" width="640">

**The [Zyplux](https://zyplux.ai) platform monorepo** — one source of truth for the org's shared tooling and standards, published to npm, PyPI, and GHCR and consumed by every product repo.

</div>

## Published packages

| Package                                          | Registry | What it is                                                                       |
| ------------------------------------------------ | -------- | -------------------------------------------------------------------------------- |
| [zyplux-cerberus](apps/cerberus)                 | PyPI     | 🐺 Org-invariant linter: CI workflows, justfiles, CODEOWNERS, coverage, releases |
| [@zyplux/cz](apps/cz)                            | npm      | Repo automation CLI: releases, PR flow, cleanup                  |
| [totchef](apps/totchef)                          | PyPI     | 🧑‍🍳 Declarative machine setup: write a recipe, run one command                    |
| [@zyplux/eslint-config](packages/eslint-config)  | npm      | Shared ESLint flat config and custom rules                                       |
| [@zyplux/tsconfig](packages/tsconfig)            | npm      | Shared TypeScript presets                                                        |
| [@zyplux/util](packages/util-ts)                 | npm      | Node utilities: assertions, polling, zod-validated parsing, git/gh shell harness |
| [zyplux-util](packages/util_py)                  | PyPI     | Python counterpart of the shared utilities                                       |
| [@zyplux/spectra](packages/spectra)         | npm      | Vitest fixtures, matchers, polling, and journal reporting                            |
| [setup-pm](apps/setup-pm) | GitHub | Cached pnpm and uv setup for dual workspaces |

Each package's README covers usage. The [release workflow](.github/workflows/release.yml) publishes configured versions automatically on pushes to `main`, using CZ to select pending targets from [release-targets.toml](release-targets.toml). Complete releases are skipped; failed publications and missing GitHub releases are retried. Registry artifacts have concurrency groups per version; action publications share a group to protect their moving major tags. CI and version-bump enforcement run on pull requests. The release workflow also supports manual retries on `main` and per-tag GitHub release events.

For releasable changes, run `pnpm run change`, then `pnpm release:prepare` before review. Each GitHub release contains its target version's reviewed changelog entry. See the [Changesets workflow](.changeset/README.md).

## Develop

The [setup-pm action](apps/setup-pm/README.md) provides cached pnpm and uv toolchains with locked installs for consuming repositories. Reference it as `zyplux/zyplux/setup-pm@v1`.

Dual workspace: pnpm (TS) + uv (Python), orchestrated by [just](https://github.com/casey/just).

```sh
just install   # both workspaces
just check     # full gate: install, knip, typecheck, lint, test, cerberus
```

Run `just` for the full recipe list. This repo is the org's quality reference — it dogfoods every new strict check first (see [cerberus.toml](cerberus.toml)), and `just check` must pass clean.
