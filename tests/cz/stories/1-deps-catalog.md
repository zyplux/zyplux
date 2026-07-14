# 1. [Cataloging external dependencies and their source repositories](1-deps-catalog.test.ts)

## 1.1 scanning workspace manifests for declared dependency names

1. collects deduplicated npm dependency names
2. collects deduplicated pypi dependency names

## 1.2 excluding internal workspace packages from declared dependency names

1. excludes an internal npm package from its own dependency list
2. excludes an internal pypi package from its own dependency list

## 1.3 resolving a dependency name to its source repository

1. resolves a package to its source repo via deps dev
2. falls back to the npm registry when deps dev has no source repo
3. falls back to pypi project urls when deps dev has no source repo
4. reports the dependency as unresolved when no source repo is found anywhere
5. falls back to a deps dev links entry when there is no related project

## 1.4 collecting the external repos a workspace depends on

1. collects deduplicated source repos for resolved dependencies
2. excludes repos that belong to the scanned workspace itself
3. reports dependencies it could not resolve to a repo

## 1.5 skipping manifest files that fail to parse

### 1.5.1 skips package.json and pyproject.toml files that fail to parse, keeping the rest
