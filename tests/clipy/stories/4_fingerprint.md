# 4. [Preparing a repository fingerprint](test_4_fingerprint.py)

## 4.1 refreshing repository metadata

### 4.1.1 prepares releases then generates the graph before measuring it

### 4.1.2 skips release preparation without targets

### 4.1.3 resolves explicit and nested paths to the repository root

### 4.1.4 fingerprints release contents after generating reports

Reports admitted by a root Action or container context are written before Airlock calculates release fingerprints. Package archives are built once.

## 4.2 stopping on failures

### 4.2.1 stops before generating reports when preparation fails

### 4.2.2 reports invalid targets before starting preparation
