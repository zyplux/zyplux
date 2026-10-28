# 39. [Preparing a repository fingerprint](test_39_fingerprint.py)

## 39.1 refreshing repository metadata

### 39.1.1 prepares releases then generates the graph before measuring it

### 39.1.2 skips release preparation without targets

### 39.1.3 resolves explicit and nested paths to the repository root

### 39.1.4 fingerprints release contents after generating reports

Reports admitted by a root Action or container context are written before Airlock calculates release fingerprints. Package archives are built once.

## 39.2 stopping on failures

### 39.2.1 stops before generating reports when preparation fails

### 39.2.2 reports invalid targets before starting preparation
