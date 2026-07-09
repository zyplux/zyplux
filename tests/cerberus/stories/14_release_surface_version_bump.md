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

### 14.4.1 passes when the current version is ahead of the latest published release

### 14.4.2 fails when the current version trails the latest published release

## 14.5 requiring a bump when the release surface changed

### 14.5.1 passes when the release surface is unchanged since the latest release

### 14.5.2 fails and names the required bump when the surface changed without one

### 14.5.3 errors when the surface diff cannot be computed
