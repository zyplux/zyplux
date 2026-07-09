# 31. [Enforcing the fixture role layout](test_31_fixture_roles_ts.py)

A torn-out TypeScript test suite (`tests/<basename>` paired with a workspace member `<dir>/<basename>`) keeps its fixtures in role modules under `fixtures/` — arrange builds the world, act drives the subject, assert verifies — composed by `fixtures/index.ts`. The `fixture_roles_ts` bite pins the two load-bearing facts: the suite's `#fixtures` alias targets `./fixtures/index.ts` (so the composer is the only door story tests enter through, with `fixtures/act.ts` present beside it), and the subject package is imported only by `act.ts`, its `./contracts` seam excepted. The story-file side of the discipline — tests importing workspace code only through `#` aliases — belongs to the `cli_ts_test_seam`/`lib_ts_test_seam` bites.

## 31.1 scoping the check to torn-out story suites

### 31.1.1 skips repos with no typescript packages

### 31.1.2 skips workspaces with no torn-out story suite

A co-located or missing stories directory leaves nothing for this bite; suites are recognized by `tests/<basename>/stories/*.test.ts` files inside a workspace member.

### 31.1.3 checks the alias even when no subject package matches the suite

A suite whose basename pairs with no workspace member still owes the role layout; only the act-only import rule is vacuous without a subject.

## 31.2 requiring the fixtures alias to target the index composer

### 31.2.1 passes a suite with the role layout

### 31.2.2 fails a fixtures alias pointing at a single fixtures file

### 31.2.3 fails a suite that declares no fixtures alias

### 31.2.4 fails a suite missing the act module

## 31.3 confining subject package imports to the act module

### 31.3.1 fails a non-act fixture module importing the subject package

### 31.3.2 allows any fixture module to import the subject contracts seam

### 31.3.3 fails a non-act fixture module importing a subject subpath

### 31.3.4 allows non-act fixture modules to import other workspace packages

Sibling workspace libraries (the shared test-fixtures harness, utility packages) are not the suite's subject; arrange and assert may lean on them freely.
