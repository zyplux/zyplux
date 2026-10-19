# 14. [Requiring a published target's version to be bumped whenever its release surface changes](test_14_release_surface_version_bump.py)

## 14.1 reading a repo's release manifest

### 14.1.1 skips repos that publish nothing

### 14.1.2 errors when the release manifest is malformed

### 14.1.3 errors when the manifest has no target array

### 14.1.4 errors when a target has an unknown kind

## 14.2 reading a target's current version

### 14.2.1 fails when the version file is missing

### 14.2.2 fails when the version file is not valid json

### 14.2.3 fails when no version is found in the version file

### 14.2.4 fails when the declared version is not semver

### 14.2.5 reads the version via the target regex

## 14.3 finding a target's latest published release

### 14.3.1 treats a target with nothing published as not yet released

### 14.3.2 fails when the current version trails the published one

### 14.3.3 errors when the published version is not semver

### 14.3.4 errors when the published version cannot be determined

## 14.4 comparing the current version against the latest published release

### 14.4.1 passes when the current version is one step ahead of the latest published release

### 14.4.2 fails when the current version trails the latest published release

### 14.4.3 fails when the current version skips ahead of the latest published release

## 14.5 requiring a bump when the release surface changed

### 14.5.1 passes when the release surface is unchanged since the latest release

### 14.5.2 fails and names the required bump when the surface changed without one

### 14.5.3 errors when the surface diff cannot be computed

## 14.6 validating private GitHub npm packages

### 14.6.1 reads a private github package using publish config

### 14.6.2 errors when private registry credentials are missing

### 14.6.3 errors when the npm registry is unsupported

### 14.6.4 errors when publish config has no registry string

### 14.6.5 accepts supported registry urls with a trailing slash

### 14.6.6 prefers the package scopes registry setting

## 14.7 requiring a bump against the pull request target branch

### 14.7.1 passes when the release surface matches the target branch

### 14.7.2 rejects reusing a target branch version before publication

### 14.7.3 passes when changed surface has a new target branch version

### 14.7.4 errors when the target branch version file is invalid json

### 14.7.5 accepts a target introduced by the pull request

### 14.7.6 errors when target branch history is unavailable

### 14.7.7 errors when the target branch version is not semver

### 14.7.8 accepts one step from an unpublished target branch version

### 14.7.9 rejects skipping steps from an unpublished target branch version

### 14.7.10 uses the published baseline when it is newer than the target branch

### 14.7.11 accepts an unchanged unpublished target branch version

### 14.7.12 accepts one step before the first publication

### 14.7.13 rejects skipping steps before the first publication

### 14.7.14 reads the base version with its own extractor

### 14.7.15 checks the base version when its file moves

### 14.7.16 distinguishes targets that share a version file

### 14.7.17 errors when an existing base target has no version file
