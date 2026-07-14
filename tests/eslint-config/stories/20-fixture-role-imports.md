# 20. [Confining subject imports to arrange.ts and act.ts](20-fixture-role-imports.test.ts)

A torn-out test suite's fixture role modules (`fixtures/arrange.ts` builds the world, `fixtures/act.ts` drives the subject, `fixtures/assert.ts`/`matchers.ts` verify) share one directory, so only an import-boundary check — not file shape — can tell them apart. The `fixture-role-imports` rule takes the suite's subject package name as an option and reports it (or any of its subpaths) imported from anything other than `arrange.ts` or `act.ts`; the subject's `/contracts` seam is exempt everywhere, since it carries no behavior. The shipped `zyplux()` config resolves the `subject` option itself, once per `tests/<basename>` suite, from the workspace dependency its own package.json names it after — so this rule needs no editor-side lookup of sibling files.

## 20.1 confining the subject to arrange and act

### 20.1.1 fails a fixture module other than arrange or act importing the subject

### 20.1.2 fails a fixture module importing a subject subpath

### 20.1.3 fails a fixture module re-exporting from the subject

### 20.1.4 fails a fixture module star-exporting the subject

### 20.1.5 fails a fixture module dynamically importing the subject

### 20.1.6 allows any fixture module to import the subject's contracts seam

### 20.1.7 allows a fixture module to import an unrelated package

## 20.2 wiring the subject option from each suite's manifest

### 20.2.1 resolves this suite's own subject package from its package.json

### 20.2.2 pairs a suite by workspace directory, not by its own package name

`tests/util-ts` pairs with `packages/util-ts`, published as `@zyplux/util` — a directory basename match, not a name derived from the suite's own `@zyplux/tests-util-ts`.
