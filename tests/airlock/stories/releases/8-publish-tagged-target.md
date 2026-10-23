# 8. [Publishing the target that owns a release tag](8-publish-tagged-target.test.ts)

## 8.1 skipping an already-published target

### 8.1.1 logs and does nothing when the tag's version is already published

## 8.2 publishing to each registry kind

### 8.2.1 publishes an npm target with native packing and availability waiting

### 8.2.2 builds and publishes incomplete PyPI releases using isolated artifacts

### 8.2.3 requires GH_TOKEN before pushing a ghcr target
### 8.2.4 requires GITHUB_ACTOR before pushing a ghcr target

### 8.2.5 publishes a versioned ghcr image and its release manifest

### 8.2.6 propagates native npm publication failures

### 8.2.7 removes GHCR credentials after a successful login when publication fails

## 8.3 publishing a private GitHub npm package

### 8.3.1 authenticates the configured registry and lets pnpm apply publishConfig

### 8.3.2 rejects missing credentials before checking a private registry

### 8.3.3 rejects registry failures without attempting publication

### 8.3.4 rejects unsupported registry destinations before making a request

### 8.3.5 accepts supported registry URLs with a trailing slash

### 8.3.6 prefers the package scope’s registry setting

### 8.3.7 checks the requested version in registry package metadata

### 8.3.8 rejects malformed package metadata without attempting publication

## 8.4 completing GitHub release metadata after publication

### 8.4.1 publishes only missing artifacts and creates only missing GitHub releases at HEAD

### 8.4.2 leaves GitHub release metadata unpublished when the registry rejects publication

### 8.4.3 rebuilds incomplete GHCR releases from a pushed digest
