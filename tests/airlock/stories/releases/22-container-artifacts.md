# 22. [Container releases](22-container-artifacts.test.ts)

## 22.1 publishing standard container releases

### 22.1.1 builds from the declared Dockerfile and context and uploads a digest-pinned manifest

### 22.1.2 rebuilds unfinished releases despite an existing image tag

### 22.1.3 keeps releases unpublished and removes credentials when image publication fails

### 22.1.4 preserves a finalized release and its manifest

### 22.1.5 rejects a finalized release whose image is missing without changing its manifest

### 22.1.6 requires the pushed image in the registry before creating its release

### 22.1.7 leaves the release as a draft when manifest upload fails

## 22.2 validating container releases

### 22.2.1 requires repository-relative build paths

### 22.2.2 rejects unsupported custom builder declarations

### 22.2.3 requires release finalization for container publication

### 22.2.4 rejects published container releases with missing manifests during planning

### 22.2.5 rejects malformed pushed digests before uploading the manifest
