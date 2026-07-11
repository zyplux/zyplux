# 12. [Running workspace tests in parallel](12-parallel-workspace-tests.test.ts)

## 12.1 running both workspaces in parallel

### 12.1.1 runs vitest and pytest and prints the JS log before the Python log

### 12.1.2 fails when the JS tests fail, still printing both logs

### 12.1.3 fails when the Python tests fail

### 12.1.4 passes when pytest collects no tests

## 12.2 filtering by test name

### 12.2.1 forwards the name filter and skips coverage on both runners

### 12.2.2 passes when the filter matches nothing in either workspace

### 12.2.3 rejects a filter that reduces to an empty pytest keyword expression instead of silently matching everything

## 12.3 workspace detection

### 12.3.1 runs only vitest when only package.json is present

### 12.3.2 runs only pytest when only pyproject.toml is present

### 12.3.3 fails when neither workspace manifest is present

## 12.4 keeping the JS runner colored despite AI-agent auto-detection

### 12.4.1 clears the env vars vitest uses to auto-disable color
