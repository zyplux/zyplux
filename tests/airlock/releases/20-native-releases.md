# 20. [Native workspace releases](test_20_native_releases.py)

## 20.1 native npm publication

### 20.1.1 repairs missing github releases without republishing existing versions

Native pnpm packs each package once and publishes the inspected archive with registry availability checks. GitHub release repair also covers earlier successful uploads.

### 20.1.2 propagates publication failure and permits a successful retry

### 20.1.3 rejects mismatched or private workspace targets before publishing

### 20.1.4 rejects targets excluded from the workspace before publishing

### 20.1.5 requires the requested version in the registry before creating a github release

## 20.2 shared action release plans

### 20.2.1 writes pending matrices to github outputs

### 20.2.2 keeps incomplete pypi releases pending even when their github release exists

## 20.4 recovering PyPI publication

### 20.4.1 retries a partial upload before creating its github release

### 20.4.2 stops before building or creating a release when pypi metadata is invalid
