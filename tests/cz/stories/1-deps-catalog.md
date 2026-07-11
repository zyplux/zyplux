# 1. [Cataloging external dependencies and their source repositories](1-deps-catalog.test.ts)

## 1.1 scanning workspace manifests for declared dependency names

### 1.1.1 collects npm dependency names from bun catalogs

### 1.1.2 collects python dependency names from project dependencies and dependency groups

### 1.1.3 excludes internal workspace packages from both ecosystems

### 1.1.4 reports sorted deduplicated names for each ecosystem

## 1.2 resolving a dependency name to its source repository

1. resolves a package to its source repo via deps dev
2. falls back to the npm registry when deps dev has no source repo
3. falls back to pypi project urls when deps dev has no source repo
4. reports the dependency as unresolved when no source repo is found anywhere
5. falls back to a deps dev links entry when there is no related project

## 1.3 collecting the external repos a workspace depends on

### 1.3.1 collects deduplicated sorted source repos for resolved dependencies

### 1.3.2 excludes repos that belong to the scanned workspace itself

### 1.3.3 reports dependencies it could not resolve to a repo

## 1.4 skipping manifest files that fail to parse

### 1.4.1 skips package.json and pyproject.toml files that fail to parse, keeping the rest
