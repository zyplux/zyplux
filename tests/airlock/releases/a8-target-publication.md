# a8. [Publishing release artifacts](a8_target_publication_test.py)

## a8.1 skipping an already-published target

### a8.1.1 logs and does nothing when the tags version is already published

## a8.2 publishing to each registry kind

### a8.2.1 publishes an npm target with native packing and availability waiting

### a8.2.2 builds and publishes incomplete pypi releases using isolated artifacts

### a8.2.3 requires gh token before pushing a ghcr target
### a8.2.4 requires github actor before pushing a ghcr target

### a8.2.5 publishes a versioned ghcr image and its release manifest

### a8.2.6 propagates native npm publication failures

### a8.2.7 removes ghcr credentials after a successful login when publication fails

## a8.3 publishing a private GitHub npm package

### a8.3.1 authenticates the configured registry and lets pnpm apply publishconfig

### a8.3.2 rejects missing credentials before checking a private registry

### a8.3.3 rejects registry failures without attempting publication

### a8.3.4 rejects unsupported registry destinations before making a request

### a8.3.5 accepts supported registry urls with a trailing slash

### a8.3.6 prefers the package scopes registry setting

### a8.3.7 checks the requested version in registry package metadata

### a8.3.8 rejects malformed package metadata without attempting publication

## a8.4 completing GitHub release metadata after publication

### a8.4.1 publishes only missing artifacts and creates only missing github releases at head

### a8.4.2 leaves github release metadata unpublished when the registry rejects publication

### a8.4.3 rebuilds incomplete ghcr releases from a pushed digest
