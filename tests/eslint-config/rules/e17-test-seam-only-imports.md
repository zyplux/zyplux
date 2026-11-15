# e17. [Keeping story-test imports behind the test seam](e17-test-seam-only-imports.test.ts)

## e17.1 allowing the seam import

1. allows describe, expect, and test from the suite API
2. allows a variant test aliased to test
3. allows a type-only import from the suite API
4. allows a mixed type and value import from the suite API

## e17.2 flagging any module beyond the suite API

1. flags a node builtin
2. flags a third-party module
3. flags a type-only import from a third-party module
4. flags a workspace package import
5. flags a workspace package subpath import
6. flags a side-effect import of a relative file path
7. flags a re-export of a relative file path
8. flags a dynamic import of a workspace package

## e17.3 flagging value bindings beyond describe, expect, and test

1. flags another named value beyond the seam vocabulary
2. flags a helper renamed to test
3. flags a default import of the suite API
4. flags a namespace import of the suite API

## e17.4 scoping the rule to tests in the shipped config

### e17.4.1 enables the rule for test files inside and outside stories

The shipped config covers `.test.ts` and `.test.tsx` throughout the repository.

## e17.5 using a local domain module

Domain stories import their test API from the module named after their directory: `tests/api` uses `./api.ts`. Helpers and subject packages remain behind that test API.

### e17.5.1 allows the module named after the story directory

### e17.5.2 allows fixture types and aliases of actual API bindings

### e17.5.3 flags a helper imported directly into a domain story

### e17.5.4 flags extra value bindings from a domain module

### e17.5.5 flags a module named after a parent domain

### e17.5.6 flags dynamic imports of a domain helper
