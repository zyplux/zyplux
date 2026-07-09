# 5. [Keeping .rumdl.toml on the org-canonical rule config](test_5_rumdl_canonical_config.py)

## 5.1 enforcing the canonical rule config

### 5.1.1 passes when the config matches canonical

### 5.1.2 passes when a repo-specific exclude list is set

### 5.1.3 fails when the rule config differs from canonical

### 5.1.4 fails when no config file exists

### 5.1.5 errors when the config cannot be parsed

## 5.2 fixing the config automatically

### 5.2.1 creates a canonical config when none exists

### 5.2.2 rewrites a non-canonical config to canonical form preserving exclude

### 5.2.3 rewrites a non-canonical config without an exclude to the exact canonical text

### 5.2.4 passes when re-checked after being fixed
