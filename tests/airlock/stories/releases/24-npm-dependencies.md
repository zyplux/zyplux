# 24. [Npm publication dependencies](test_24_npm_dependencies.py)

## 24.1 isolating npm publication jobs

### 24.1.1 plans separate jobs without packing packages or discovering dependencies

### 24.1.2 confines npm publication failures to their jobs

### 24.1.3 rejects invalid workspace dependencies

### 24.1.5 rejects publish only lifecycle hooks before packing

### 24.1.6 encodes target names in archive filenames

## 24.2 waiting for installable dependencies

### 24.2.1 waits for dependency metadata and tarball visibility before uploading

### 24.2.3 propagates registry authorization errors before uploading

### 24.2.4 waits for existing version tarballs before repairing github releases

## 24.3 packed publication dependencies

### 24.3.1 publishes a bundle after its packing hook removes private workspace dependencies

### 24.3.2 waits for the real package behind an npm alias

### 24.3.3 skips workspace waits for bundled or incompatible dependencies

### 24.3.4 rejects packing hooks that change the package identity

## 24.4 validating publication cycles

### 24.4.1 rejects reachable unpublished cycles without packing peers

### 24.4.2 uses prepared packing hook metadata to break apparent source cycles

### 24.4.3 rejects invalid prepared peer dependencies without packing them

### 24.4.4 accepts omitted or empty dependencies and omits them during preparation

### 24.4.5 rejects omitting a real dependency before publication

### 24.4.6 resolves exact dependency versions from target version sources
