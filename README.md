# <img src="docs/assets/logo.svg" alt="" width="24"> zyplux

<div align="center">

<img src="docs/assets/og.png" alt="Zyplux — Neural Intelligence Systems" width="640">

**The [Zyplux](https://zyplux.ai) platform monorepo** — one source of truth for the org's shared tooling and standards, published to npm, PyPI, and GHCR and consumed by every product repo.

</div>

## Published packages

| Package                                          | Registry | What it is                                                                       |
| ------------------------------------------------ | -------- | -------------------------------------------------------------------------------- |
| [zyplux-cerberus](apps/cerberus)                 | PyPI     | 🐺 Org-invariant linter: CI workflows, justfiles, CODEOWNERS, coverage, releases |
| [@zyplux/cz](apps/cz)                            | npm      | Repo automation CLI: PR flow, workspace maintenance, cleanup                  |
| [zyplux-airlock](apps/airlock) | PyPI | Release preparation and publication with native pnpm |
| [totchef](apps/totchef)                          | PyPI     | 🧑‍🍳 Declarative machine setup: write a recipe, run one command                    |
| [@zyplux/eslint-config](packages/eslint-config)  | npm      | Shared ESLint flat config and custom rules                                       |
| [@zyplux/tsconfig](packages/tsconfig)            | npm      | Shared TypeScript presets                                                        |
| [@zyplux/util](packages/util-ts)                 | npm      | Node utilities: assertions, polling, zod-validated parsing, git/gh shell harness |
| [zyplux-util](packages/util_py)                  | PyPI     | Python counterpart of the shared utilities                                       |
| [@zyplux/spectra](packages/spectra)         | npm      | Vitest fixtures, matchers, polling, and journal reporting                            |
| [setup-pm](apps/action-setup-pm) | GitHub | Cached pnpm and uv setup for dual workspaces |
| [Airlock](apps/action-airlock) | GitHub | Plan and publish reviewed workspace releases |

Each package's README covers usage. Follow the [Airlock release workflow](apps/airlock/README.md) to prepare reviewed versions and automatically publish the targets in [airlock-targets.toml](airlock-targets.toml).

For releasable changes, run `pnpm change`, then `pnpm release:prepare` before review. Each GitHub release contains its target version's reviewed changelog entry. See the [release workflow](.changeset/README.md).

## Develop

The [setup-pm action](apps/action-setup-pm/README.md) provides cached pnpm and uv toolchains with locked installs for consuming repositories. Reference it as `zyplux/zyplux/apps/action-setup-pm@setup-pm-v1`.

Dual workspace: pnpm (TS) + uv (Python), orchestrated by [just](https://github.com/casey/just).

```sh
just install   # both workspaces
just check     # full gate: install, knip, typecheck, lint, test, cerberus
```

Run `just` for the full recipe list. This repo is the org's quality reference — it dogfoods every new strict check first (see [cerberus.toml](cerberus.toml)), and `just check` must pass clean.
