# 19. [Requiring a vitest coverage floor of at least 90%](test_19_vitest.py)

## 19.1 scoping the coverage checks to repos with a root vitest config

### 19.1.1 ignores a nested vitest config that is not at the repo root

## 19.2 requiring the config file to be readable and well formed

### 19.2.1 errors when the root vitest config cannot be read

### 19.2.2 fails when the coverage block is unterminated

## 19.3 requiring the coverage block to declare thresholds

### 19.3.1 fails when the config has no coverage block

### 19.3.2 fails when the coverage block has no thresholds

## 19.4 requiring every threshold metric to meet the required floor

### 19.4.1 fails and names the metric when a threshold is below the required floor

### 19.4.2 fails when a threshold metric is missing

## 19.5 passing a fully compliant config

### 19.5.1 passes when every threshold metric meets the required floor
