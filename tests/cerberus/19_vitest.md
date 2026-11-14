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

### 19.4.3 rejects functions in numeric threshold fields

## 19.5 passing a fully compliant config

### 19.5.1 passes when every threshold metric meets the required floor

### 19.5.2 resolves local constants typed objects and vitest config helpers

### 19.5.3 rejects unresolved cycles mutable configs and unknown transformations

### 19.5.4 ignores coverage in unrelated nested objects

### 19.5.5 applies literal spreads in source order

### 19.5.6 trusts config helpers only from vitest or vite

## 19.6 requiring coverage collection

### 19.6.1 requires coverage collection in config or the root test command

### 19.6.2 requires explicit collection when coverage enabled is absent

### 19.6.3 CLI coverage flags override enabled configuration

### 19.6.4 preserves coverage validation when the test manifest is malformed
