# a22. [Container releases](a22_container_artifacts_test.py)

## a22.1 publishing standard container releases

### a22.1.1 builds from the declared dockerfile and context and uploads a digest pinned manifest

### a22.1.2 rebuilds unfinished releases despite an existing image tag

### a22.1.3 keeps releases unpublished and removes credentials when image publication fails

### a22.1.4 preserves a finalized release and its manifest

### a22.1.5 rejects a finalized release whose image is missing without changing its manifest

### a22.1.6 requires the pushed image in the registry before creating its release

### a22.1.7 leaves the release as a draft when manifest upload fails

### a22.1.8 builds with the selected adjacent ignore file

## a22.2 validating container releases

### a22.2.1 requires repository relative build paths

### a22.2.2 rejects unsupported custom builder declarations

### a22.2.4 rejects published container releases with missing manifests during planning

### a22.2.5 rejects malformed pushed digests before uploading the manifest
