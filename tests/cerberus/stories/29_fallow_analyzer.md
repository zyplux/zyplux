# 29. [Banning dead code and complexity offenders via fallow](test_29_fallow_analyzer.py)

## 29.1 scoping the check

### 29.1.1 skips repos with no package.json without running fallow

## 29.2 enforcing fallow's dead-code verdict

### 29.2.1 passes when both fallow analyses exit clean

### 29.2.2 runs fallow dead code and health non-interactively from a shielded cwd against the repo root

### 29.2.3 fails with the issue count when fallow dead-code reports issues

### 29.2.4 errors when bunx is not on PATH

## 29.3 enforcing fallow's complexity thresholds

### 29.3.1 fails listing each function fallow health flags above its thresholds

### 29.3.2 fails listing only the metrics fallow reported when coverage data is absent

## 29.4 surfacing fallow's health status line

### 29.4.1 reports fallow's health status line on a clean run

### 29.4.2 leaves the detail unset on failure so the status line appears only in the fail line

## 29.5 owning fallow's configuration

Tests are as load-bearing as production code, so the cerberus-owned config also switches off fallow's default duplicate ignores (`**/*.test.*` and friends) — no fallow analysis run under cerberus ever skips test files.

### 29.5.1 shields fallow behind a cerberus-owned config ignoring workspace dirs without a package.json

### 29.5.2 errors when package.json is not valid JSON instead of crashing

### 29.5.3 switches off fallow's default duplicate ignores so test files count

## 29.6 itemizing dead-code issues in verbose runs

By default a dead-code failure reports only the issue count and defers to a local rerun; in verbose mode the check itemizes each issue from fallow's own report — its category, location, and name — so the rerun is unnecessary.

### 29.6.1 fails itemizing each dead-code issue with its category and location in verbose mode

### 29.6.2 keeps the count-and-rerun-hint failure without verbose

## 29.7 running fallow at the version pinned in cerberus source

A bare `bunx fallow` floats to npm's latest and drifts per machine; the check invokes the exact version pinned in cerberus's `tool_pins` module, so every run — local or CI, any repo — analyzes with the same tool.

### 29.7.1 invokes fallow at the pinned version
