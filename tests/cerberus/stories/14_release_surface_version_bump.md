# 14. [Requiring a published target's version to be bumped whenever its release surface changes](test_14_release_surface_version_bump.py)

## 14.1 validating release targets and versions

### 14.1.1 rejects malformed manifests

### 14.1.2 accepts a scope with no targets

### 14.1.3 rejects missing or invalid versions

### 14.1.4 reports missing version files

### 14.1.5 reads native python versions with the configured regex

### 14.1.6 validates every target when one version is invalid

## 14.2 requiring one-step release bumps

### 14.2.1 accepts a single patch minor or major bump

### 14.2.2 rejects skipped bumps

### 14.2.3 rejects versions below the published version

### 14.2.4 permits an initial release

### 14.2.5 accepts published versions with unchanged surfaces

### 14.2.6 rejects changes to an already published version

### 14.2.7 reports unavailable release history

## 14.3 comparing pull request baselines

### 14.3.1 permits repairs to unpublished target branch versions

### 14.3.2 uses the newer published or target branch baseline

### 14.3.3 rejects regressions against an unpublished target branch version

### 14.3.4 rejects skipped bumps before first publication

### 14.3.5 allows targets introduced by the pull request

### 14.3.6 rejects malformed target branch versions

### 14.3.7 rejects unavailable target branch history

### 14.3.8 reads the base version with its own extractor and path

### 14.3.9 reports missing base version files

### 14.3.10 distinguishes targets sharing a version file

### 14.3.11 uses the github target branch by default

## 14.4 reading published release versions

### 14.4.1 follows scoped publication registries

### 14.4.2 rejects missing private registry credentials

### 14.4.3 rejects unsupported publication configuration

### 14.4.4 reports registry failures as errors

### 14.4.5 compares stable action releases across all pages

### 14.4.6 selects stable numeric container tags

## 14.5 reusing GitHub credentials for private registry reads

### 14.5.1 reads private npm metadata without manual node auth token exports

### 14.5.2 authenticates private container reads with the saved login and its actor

### 14.5.3 preserves explicitly supplied credentials and reports denied access

## 14.6 reporting through Cerberus

### 14.6.1 skips repos that publish nothing

### 14.6.2 checks the repository without an npm cli

### 14.6.3 reports manifest errors

### 14.6.4 preserves findings from multiple targets
