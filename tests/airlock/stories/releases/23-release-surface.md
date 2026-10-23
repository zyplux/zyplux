# 23. [Release surface validation](23-release-surface.test.ts)

## 23.1 validating release targets and versions

### 23.1.1 rejects malformed manifests

### 23.1.2 accepts a scope with no targets

### 23.1.3 rejects missing or invalid versions

### 23.1.4 reports missing version files

### 23.1.5 reads native Python versions with the configured regex

### 23.1.6 validates every target when one version is invalid

## 23.2 requiring one-step release bumps

### 23.2.1 accepts a single patch minor or major bump

### 23.2.2 rejects skipped bumps

### 23.2.3 rejects versions below the published version

### 23.2.4 permits an initial release

### 23.2.5 accepts published versions with unchanged surfaces

### 23.2.6 rejects changes to an already published version

### 23.2.7 reports unavailable release history

## 23.3 comparing pull request baselines

### 23.3.1 permits repairs to unpublished target branch versions

### 23.3.2 uses the newer published or target branch baseline

### 23.3.3 rejects regressions against an unpublished target branch version

### 23.3.4 rejects skipped bumps before first publication

### 23.3.5 allows targets introduced by the pull request

### 23.3.6 rejects malformed target branch versions

### 23.3.7 rejects unavailable target branch history

### 23.3.8 reads the base version with its own extractor and path

### 23.3.9 reports missing base version files

### 23.3.10 distinguishes targets sharing a version file

### 23.3.11 uses the GitHub target branch by default

## 23.4 reading published release versions

### 23.4.1 follows scoped publication registries

### 23.4.2 rejects missing private registry credentials

### 23.4.3 rejects unsupported publication configuration

### 23.4.4 reports registry failures as errors

### 23.4.5 compares stable action releases across all pages

### 23.4.6 selects stable numeric container tags

### 23.4.7 prints readable findings without json mode
