# 32. [Enforcing pnpm's release-age quarantine](test_32_pnpm_release_age.py)

## 32.1 scoping the policy to pnpm workspaces

### 32.1.1 skips repos without a pnpm workspace

## 32.2 requiring the organization release-age policy

### 32.2.1 accepts the release age policy

### 32.2.2 requires a one day quarantine

### 32.2.3 requires stale exclusion pruning

### 32.2.4 rejects external package exclusions

### 32.2.5 accepts no exclusions

## 32.3 rejecting malformed workspace manifests

### 32.3.1 errors on invalid yaml
