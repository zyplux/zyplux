# 17. [Keeping story-test imports behind the test seam](17-test-seam-only-imports.test.ts)

## 17.1 allowing the seam import

1. allows describe, expect, and test from the fixtures alias
2. allows a variant test aliased to test
3. allows a type-only import from the fixtures alias
4. allows a mixed type and value import from the fixtures alias

## 17.2 flagging any module beyond the fixtures alias

1. flags a node builtin
2. flags a third-party module
3. flags a type-only import from a third-party module
4. flags a workspace package import
5. flags a workspace package subpath import
6. flags a side-effect import of a relative file path
7. flags a re-export of a relative file path
8. flags a dynamic import of a workspace package

## 17.3 flagging value bindings beyond describe, expect, and test

1. flags another named value beyond the seam vocabulary
2. flags a rename away from the seam vocabulary
3. flags a default import of the fixtures alias
4. flags a namespace import of the fixtures alias

## 17.4 scoping the rule to story tests in the shipped config

### 17.4.1 enables the rule only for story test files
