# 8. [Publishing the target that owns a release tag](8-publish-tagged-target.test.ts)

## 8.1 skipping an already-published target

### 8.1.1 logs and does nothing when the tag's version is already published

## 8.2 publishing to each registry kind

### 8.2.1 packs and publishes an npm target

### 8.2.2 builds and publishes a pypi target

1. requires GH_TOKEN before pushing a ghcr target
2. requires GITHUB_ACTOR before pushing a ghcr target

### 8.2.4 tags and pushes a versioned and latest ghcr image
