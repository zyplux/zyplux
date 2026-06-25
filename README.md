# zyp-cerberus

The zyplux organization's platform monorepo: it publishes shared tooling to npm and PyPI, and the product monorepos consume it. One source of truth for the org's standards, so they stay in lockstep instead of drifting per repo.

It also hosts the org's publishable quality checks. Today:

| Package                                         | What it is                                                                                                |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| [cerberus](apps/cerberus)                       | CLI that verifies org-wide repository invariants — CI workflows, CODEOWNERS, secrets, justfiles           |
| [@zyplux/eslint-config](packages/eslint-config) | Shared ESLint flat config and custom rules                                                                |

More shared packages will land here over time — additional configs, scaffolding tools, and UI. See each package's README for usage. cerberus is a Python (uv) workspace; eslint-config is a TypeScript (bun) workspace.

## Develop

```sh
just install   # bun + uv workspaces
just check     # install, knip, typecheck, lint, test — both workspaces
```

Individual recipes: `just lint`, `just typecheck`, `just test`, `just knip`. Run `just` for the full list.
