# 14. [Requiring a published target's version to be bumped whenever its release contents change](test_14_release_surface_version_bump.py)

## 14.1 validating release targets and versions

### 14.1.1 rejects malformed manifests

### 14.1.2 accepts a scope with no targets

### 14.1.3 rejects missing or invalid versions

### 14.1.4 reports missing version files

### 14.1.5 reads native python versions with the configured regex

### 14.1.6 validates every target when one version is invalid

### 14.1.7 reports invalid version regexes

### 14.1.8 rejects version sources outside the selected repository

## 14.2 requiring one-step release bumps

### 14.2.1 accepts a single patch minor or major bump

### 14.2.2 rejects skipped bumps

### 14.2.3 rejects versions below the published version

### 14.2.4 permits an initial release

### 14.2.5 accepts published versions with unchanged contents

### 14.2.6 rejects changes to an already published version

### 14.2.7 reports unavailable release history

## 14.3 comparing pull request baselines

### 14.3.1 compares current versions against the latest baseline

### 14.3.3 rejects regressions against an unpublished target branch version

### 14.3.4 rejects skipped bumps before first publication

### 14.3.5 allows targets introduced by the pull request

### 14.3.6 rejects malformed target branch versions

### 14.3.7 rejects unavailable target branch history

### 14.3.8 reads the base version with its own extractor and path

### 14.3.9 reports missing base version files

### 14.3.10 distinguishes targets sharing a version file

### 14.3.11 uses the github target branch by default

### 14.3.12 reads a shared baseline version file once

## 14.4 reading published release versions

### 14.4.4 reports release history failures as errors

### 14.4.5 compares stable action releases across all pages

### 14.4.6 uses successful container releases

### 14.4.7 reads release history once for all targets

### 14.4.8 rejects action repositories outside the checkout

## 14.6 reporting through Cerberus

### 14.6.1 skips repos that publish nothing

### 14.6.2 checks the repository without an npm cli

### 14.6.3 reports manifest errors

### 14.6.4 preserves findings from multiple targets

## 14.7 comparing packaged contents with release fingerprints

### 14.7.1 accepts package contents matching the successful release tag

### 14.7.2 detects changes even after the pr fingerprint is refreshed

### 14.7.3 uses finalized stable releases instead of registry versions

### 14.7.4 accepts the first fingerprint before a release baseline exists

### 14.7.6 requires bumps for changed action and container inputs

## 14.8 preserving partially published versions

### 14.8.1 preserves target branch fingerprints after any registry artifact is uploaded

### 14.8.2 allows identical contents to repair a missing github release

### 14.8.3 allows same version repairs before any registry artifact exists

### 14.8.4 reports registry errors during repair validation
