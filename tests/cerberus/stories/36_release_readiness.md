# 36. [Release readiness](test_36_release_readiness.py)

## 36.1 checking the selected repository

### 36.1.1 skips repositories without release targets

### 36.1.2 validates the selected repository without changing release metadata

### 36.1.3 rejects malformed release manifests

### 36.1.4 resolves dependencies inside the selected repository when invoked elsewhere

## 36.2 validating prepared release metadata

### 36.2.1 rejects unconsumed change intents

### 36.2.2 rejects inconsistent python tracking manifests

### 36.2.3 rejects missing or empty current release notes

## 36.3 verifying prepared contents

### 36.3.1 rejects stale fingerprints

### 36.3.2 reports build failures

### 36.3.3 rejects missing fingerprints
