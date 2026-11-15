# a24. [Npm publication dependencies](a24_npm_dependencies_test.py)

## a24.1 isolating npm publication jobs

### a24.1.1 plans separate jobs without packing packages or discovering dependencies

### a24.1.2 confines npm publication failures to their jobs

### a24.1.3 rejects invalid workspace dependencies

### a24.1.5 rejects publish only lifecycle hooks before packing

### a24.1.6 encodes target names in archive filenames

## a24.2 waiting for installable dependencies

### a24.2.1 waits for dependency metadata and tarball visibility before uploading

### a24.2.3 propagates registry authorization errors before uploading

### a24.2.4 waits for existing version tarballs before repairing github releases

## a24.3 packed publication dependencies

### a24.3.1 publishes a bundle after its packing hook removes private workspace dependencies

### a24.3.2 waits for the real package behind an npm alias

### a24.3.3 skips workspace waits for bundled or incompatible dependencies

### a24.3.4 rejects packing hooks that change the package identity

## a24.4 validating publication cycles

### a24.4.1 rejects reachable unpublished cycles without packing peers

### a24.4.2 uses prepared packing hook metadata to break apparent source cycles

### a24.4.3 rejects invalid prepared peer dependencies without packing them

### a24.4.4 accepts omitted or empty dependencies and omits them during preparation

### a24.4.5 rejects omitting a real dependency before publication

### a24.4.6 resolves exact dependency versions from target version sources
