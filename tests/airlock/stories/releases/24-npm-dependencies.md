# 24. [Npm publication dependencies](24-npm-dependencies.test.ts)

## 24.1 isolating npm publication jobs

### 24.1.1 plans separate jobs without packing packages or discovering dependencies

### 24.1.2 confines npm publication failures to their jobs

### 24.1.3 rejects invalid workspace dependencies

### 24.1.4 rejects cycles when publishing several npm targets in one command

## 24.2 waiting for installable dependencies

### 24.2.1 waits for dependency metadata and tarball visibility before uploading

### 24.2.3 propagates registry authorization errors before uploading

## 24.3 packed publication dependencies

### 24.3.1 publishes a bundle after its packing hook removes private workspace dependencies

### 24.3.2 waits for the real package behind an npm alias

### 24.3.3 publishes dependencies embedded in the archive without registry waits
