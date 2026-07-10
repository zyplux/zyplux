# 17. [Keeping story-test imports behind the test seam](17-test-seam-only-imports.test.ts)

## 17.1 allowing imports through the test seam

### 17.1.1 allows fixture aliases and node builtins

### 17.1.2 allows third-party modules, value or type

## 17.2 flagging imports that reach around the seam

### 17.2.1 flags file-path imports, including side-effect imports and re-exports

### 17.2.2 flags bare specifiers that resolve to workspace source

### 17.2.3 flags type-only and dynamic workspace imports

## 17.3 scoping the rule to story tests in the shipped config

### 17.3.1 enables the rule only for story test files
