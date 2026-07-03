# 9. [Requiring vitest as the sole test runner for TypeScript](test_9_vitest-runner.py)

## 9.1 scoping the check to repos with test tooling to configure

### 9.1.1 skips repos with no package json

## 9.2 requiring every package json test script to invoke vitest instead of bun

### 9.2.1 fails when the test script runs bun test directly

### 9.2.2 fails when a nested package manifest runs bun test

### 9.2.3 allows bun script runner invocations of the test script

### 9.2.4 treats an unparseable manifest as having no test script

## 9.3 requiring test files to import from vitest instead of bun test

### 9.3.1 fails when a test file imports from bun test

## 9.4 excluding vendored node modules from the scan

### 9.4.1 ignores bun test scripts and imports inside vendored node modules

## 9.5 passing repos that use vitest throughout

### 9.5.1 passes when the test script and test files both use vitest

## 9.6 catching bun test runner invocations outside package json

### 9.6.1 fails when a justfile recipe runs bun test

### 9.6.2 fails when a workflow run step runs bun test

### 9.6.3 ignores comment lines that mention bun test
