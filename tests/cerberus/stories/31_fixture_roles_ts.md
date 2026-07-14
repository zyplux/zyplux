# 31. [Enforcing the fixture role layout](test_31_fixture_roles_ts.py)

A torn-out TypeScript test suite (`tests/<basename>` paired with a workspace member `<dir>/<basename>`) keeps its fixtures in role modules under `fixtures/` — arrange builds the world, act drives the subject, assert verifies — composed by `fixtures/index.ts`. The `fixture_roles_ts` bite pins the suite's manifest shape: the `#fixtures` alias targets `./fixtures/index.ts` (so the composer is the only door story tests enter through), with `fixtures/act.ts` present beside it. Which role modules may import the suite's subject package — arrange.ts and act.ts may, every other fixture module may not, its `./contracts` seam excepted — is enforced in-editor instead, by the `@zyplux/fixture-role-imports` ESLint rule. The story-file side of the discipline — tests importing workspace code only through `#` aliases — belongs to the `cli_ts_test_seam`/`lib_ts_test_seam` bites.

## 31.1 scoping the check to torn-out story suites

### 31.1.1 skips repos with no typescript packages

### 31.1.2 skips workspaces with no torn-out story suite

A co-located or missing stories directory leaves nothing for this bite; suites are recognized by `tests/<basename>/stories/*.test.ts` files inside a workspace member.

## 31.2 requiring the fixtures alias to target the index composer

### 31.2.1 passes a suite with the role layout

### 31.2.2 fails a fixtures alias pointing at a single fixtures file

### 31.2.3 fails a suite that declares no fixtures alias

### 31.2.4 fails a suite missing the act module
