# 1. [Discovering and reading package manifests for dependencies and repository info](1-manifest.test.ts)

## 1.1 parsing manifest text into typed shapes

### 1.1.1 parses package json text into a typed manifest and strips unknown keys

### 1.1.2 tolerates the array form of workspaces

### 1.1.3 parses pyproject toml text with pep 621 and pep 735 dependency sections and strips unknown keys

## 1.2 collecting and normalizing dependency names from a manifest

### 1.2.1 collects npm catalog and dependency field names while skipping workspace local specs

### 1.2.2 collects python requirement names across every section while dropping python itself

1. normalizes an underscored requirement name into its pep 503 canonical form
2. normalizes a dotted requirement name with a version specifier
3. returns undefined when no package name can be parsed from a requirement

## 1.3 resolving a manifest's repository url

1. reads the url from a string repository field
2. reads the url from an object repository field
3. returns undefined when no repository is declared

## 1.4 discovering manifests tracked by git

### 1.4.1 lists tracked manifests under the repo and excludes ignored paths

### 1.4.2 discovers manifests across nested repositories when the directory itself is outside any repository
