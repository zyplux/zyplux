# 13. [Matching the JS test filter against file paths and test names](13-smart-js-test-filter.test.ts)

## 13.1 resolving a filter against real test files before running

1. resolves a filter matching only a file path
2. resolves a filter matching only a test name
3. resolves a filter matching nothing
4. resolves a filter matching both the path and a test name of the same file

## 13.2 unioning matches across multiple files

### 13.2.1 runs every matched file together when different files match for different reasons

## 13.3 rejecting an invalid filter pattern

### 13.3.1 rejects an invalid regex filter with a clear error instead of crashing
