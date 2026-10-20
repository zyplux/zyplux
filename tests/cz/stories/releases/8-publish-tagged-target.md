# 8. [Publishing the target that owns a release tag](8-publish-tagged-target.test.ts)

## 8.1 skipping an already-published target

### 8.1.1 logs and does nothing when the tag's version is already published

## 8.2 publishing to each registry kind

### 8.2.1 packs and publishes an npm target

### 8.2.2 builds and publishes a pypi target

### 8.2.3 requires GH_TOKEN before pushing a ghcr target
### 8.2.4 requires GITHUB_ACTOR before pushing a ghcr target

### 8.2.5 tags and pushes a versioned and latest ghcr image

### 8.2.6 removes the temporary archive when npm publication fails

## 8.3 publishing a private GitHub npm package

### 8.3.1 authenticates the configured registry and lets npm apply publishConfig

### 8.3.2 rejects missing credentials before checking a private registry

### 8.3.3 rejects registry failures without attempting publication

### 8.3.4 rejects unsupported registry destinations before making a request

### 8.3.5 accepts supported registry URLs with a trailing slash

### 8.3.6 prefers the package scope’s registry setting

### 8.3.7 checks the requested version in GitHub package metadata

### 8.3.8 rejects malformed package metadata without attempting publication

## 8.4 completing GitHub release metadata after publication

### 8.4.1 publishes only missing artifacts and creates only missing GitHub releases at HEAD

### 8.4.2 leaves GitHub release metadata unpublished when the registry rejects publication
