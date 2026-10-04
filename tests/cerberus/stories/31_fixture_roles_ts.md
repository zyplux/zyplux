# 31. [Structuring story suites](test_31_fixture_roles_ts.py)

Each nested story directory owns a test module named after its domain: `stories/api` uses `api.ts`. Flat suites use the `#fixtures` alias targeting `fixtures/index.ts`, with `fixtures/act.ts` present. The `fixture_roles_ts` bite verifies this layout; ESLint's `test-seam-only-imports` rule keeps story imports behind the test API.

## 31.1 scoping the check to torn-out story suites

### 31.1.1 skips repos with no typescript packages

### 31.1.2 skips workspaces with no torn-out story suite

A co-located or missing stories directory leaves nothing for this bite; suites are recognized by flat or nested `.test.ts` files under `tests/<basename>/stories` inside a workspace member.

## 31.2 requiring the fixtures alias to target the index composer

### 31.2.1 passes a suite with the role layout

### 31.2.2 fails a fixtures alias pointing at a single fixtures file

### 31.2.3 fails a suite that declares no fixtures alias

### 31.2.4 fails a suite missing the act module

## 31.3 grouping stories by domain

### 31.3.1 passes a domain suite without a fixtures alias

### 31.3.2 fails a domain missing its test module

### 31.3.3 requires a test module for each nested domain

### 31.3.4 checks flat and domain layouts in the same suite
