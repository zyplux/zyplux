# 17. [Keeping story-test imports behind the test seam](17-test-seam-only-imports.test.ts)

## 17.1 allowing the seam import

### 17.1.1 allows describe, expect, and test from the fixtures alias, including a variant test aliased to test

### 17.1.2 allows type-only imports from the fixtures alias

## 17.2 flagging any module beyond the fixtures alias

### 17.2.1 flags node builtins and third-party modules

### 17.2.2 flags workspace packages and file paths, including side-effect imports and re-exports

### 17.2.3 flags dynamic imports of any module beyond the fixtures alias

## 17.3 flagging value bindings beyond describe, expect, and test

### 17.3.1 flags other named values and renames away from the seam vocabulary

### 17.3.2 flags default and namespace imports of the fixtures alias

## 17.4 scoping the rule to story tests in the shipped config

### 17.4.1 enables the rule only for story test files
