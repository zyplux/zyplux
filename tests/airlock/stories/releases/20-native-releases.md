# 20. [Native workspace releases](20-native-releases.test.ts)

## 20.1 native npm publication

### 20.1.1 filters declared targets and repairs missing GitHub releases

Native pnpm owns packing, dependency order, publication summaries and registry availability checks. GitHub release repair also covers earlier successful uploads.

### 20.1.2 propagates publication failure and permits a successful retry

## 20.2 shared action release plans

### 20.2.1 writes pending matrices to GitHub outputs

### 20.2.2 keeps incomplete PyPI releases pending even when their GitHub release exists

## 20.3 prebuilt container release assets

### 20.3.1 uploads assets to a draft before publishing the release

### 20.3.2 rejects incomplete release assets

Failed asset uploads leave a draft unpublished; published releases must already contain the required assets.

## 20.4 recovering PyPI publication

### 20.4.1 retries a partial upload before creating its GitHub release

### 20.4.2 stops before building or creating a release when PyPI metadata is invalid
