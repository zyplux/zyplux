# zyp-cerberus

Monorepo for the zyplux organization. Two workspaces:

| Package                                         | What it is                                                                                                |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| [cerberus](apps/cerberus)                       | CLI that verifies org-wide repository invariants — CI workflows, rulesets, CODEOWNERS, secrets, justfiles |
| [@zyplux/eslint-config](packages/eslint-config) | Shared ESLint flat config and custom rules                                                                |

See each package's README for usage. cerberus is a Python (uv) workspace; eslint-config is a TypeScript (bun) workspace.

## Develop

```sh
just install   # bun + uv workspaces
just check     # install, knip, typecheck, lint, test — both workspaces
```

Individual recipes: `just lint`, `just typecheck`, `just test`, `just format`, `just knip`. Run `just` for the full list.
