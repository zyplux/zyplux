# 1. [Cataloging external dependencies and their source repositories](1_deps-catalog.test.ts)

## 1.1 scanning workspace manifests for declared dependency names

### 1.1.1 collects npm dependency names from bun catalogs

### 1.1.2 collects python dependency names from project dependencies and dependency groups

### 1.1.3 excludes internal workspace packages from both ecosystems

### 1.1.4 returns sorted deduplicated names for each ecosystem

## 1.2 resolving a dependency name to its source repository

### 1.2.1 resolves a package to its source repo via deps dev

### 1.2.2 falls back to the npm registry when deps dev has no source repo

### 1.2.3 falls back to pypi project urls when deps dev has no source repo

### 1.2.4 returns undefined when no source repo is found anywhere

## 1.3 collecting the external repos a workspace depends on

### 1.3.1 collects deduplicated sorted source repos for resolved dependencies

### 1.3.2 excludes repos that belong to the scanned workspace itself

### 1.3.3 reports dependencies it could not resolve to a repo
