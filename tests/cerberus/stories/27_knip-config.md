# 27. [Governing knip configuration](test_27_knip-config.py)

## 27.1 scoping the check

### 27.1.1 skips repos with no package.json

### 27.1.2 errors when package.json cannot be parsed

### 27.1.3 errors when package.json is not an object

## 27.2 forbidding an inline package.json knip key

### 27.2.1 fails when package.json has an inline knip key

## 27.3 limiting standalone knip.json to the shared per-key allowances

### 27.3.1 fails when knip.json customizes anything beyond the allowed keys

### 27.3.2 fails when an allowed key is not a list of strings

### 27.3.3 fails when ignoreBinaries names a binary outside the shared allowance

### 27.3.4 fails when ignoreDependencies names a dependency outside the shared allowance

### 27.3.5 passes when customizations draw only from the shared allowances, ignoring $schema

### 27.3.6 passes when knip.json is absent and the repo needs no customization

### 27.3.7 errors when knip.json cannot be parsed

### 27.3.8 errors when knip.json is not an object

## 27.4 requiring an entry-exports pass scoped to unpublished workspaces

### 27.4.1 fails when knip.prod.json is missing

### 27.4.2 fails when includeEntryExports is not true

### 27.4.3 fails when ignoreWorkspaces does not match the test harness glob

### 27.4.4 fails and names an unexpected top level key

### 27.4.5 fails and names a published target missing its exemption

### 27.4.6 fails and names a non published dir wrongly exempted

### 27.4.7 passes when every published npm target is exempted and nothing else is

### 27.4.8 passes with no release-targets.toml and no workspace exemptions

### 27.4.9 errors when knip.prod.json cannot be parsed

### 27.4.10 errors when knip.prod.json is not an object

### 27.4.11 ignores a malformed release-targets.toml as no published targets

### 27.4.12 ignores a release-targets.toml whose target key is not a list

### 27.4.13 ignores non npm targets when computing published workspace dirs

### 27.4.14 requires the prod config to repeat knip.json's customizations

### 27.4.15 passes when the prod config repeats knip.json's customizations

### 27.4.16 fails and names a workspace entry with extra keys

### 27.4.17 fails when the workspaces key is not an object

### 27.4.18 allows excluding exactly the catalog issue type

### 27.4.19 fails when exclude covers anything beyond the catalog issue type
