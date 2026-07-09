# 11. [Requiring workspace dependencies to pin via catalog: or workspace](test_11_catalog_pinned_deps.py)

## 11.1 scoping the scan to bun workspaces

### 11.1.1 skips repos with no package json

### 11.1.2 skips repos whose package json is not a workspace

## 11.2 requiring every workspace dependency to pin via catalog or workspace

### 11.2.1 passes when every dependency pins via catalog or workspace

### 11.2.2 fails and names the dependency that pins a raw version

### 11.2.3 treats an unparseable manifest as declaring no dependencies

## 11.3 excluding vendored packages from the scan

### 11.3.1 ignores dependencies declared in a vendored node modules package json
