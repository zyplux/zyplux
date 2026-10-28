# 18. [Preparing reviewed releases](test_18_prepare_release.py)

## 18.1 preparing native package releases

### 18.1.1 runs pnpm versioning and uv to produce synchronized versions changelogs and lockfiles

Preparation consumes each fragment once. A repeated preparation without new fragments leaves versions and changelogs unchanged.

### 18.1.2 rejects python version drift before changing any release files

### 18.1.3 stops before python synchronization when native versioning fails

### 18.1.4 propagates a workspace dependency bump through pnpm

### 18.1.5 directs version lookups to the package publication registry

### 18.1.6 authenticates private preparation with existing github credentials

### 18.1.7 preserves explicit registry authentication

### 18.1.8 keeps public preparation independent of github credentials

### 18.1.9 prepares without a github login when no fallback is available

### 18.1.10 rejects invalid authentication without disclosing credentials

### 18.1.11 adds only missing scope credentials and honors lowercase environment precedence

### 18.1.12 adds authentication without changing dependency registry routes
