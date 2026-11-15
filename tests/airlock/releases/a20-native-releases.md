# a20. [Native workspace releases](a20_native_releases_test.py)

## a20.1 native npm publication

### a20.1.1 repairs missing github releases without republishing existing versions

Native pnpm packs each package once and publishes the inspected archive with registry availability checks. GitHub release repair also covers earlier successful uploads.

### a20.1.2 propagates publication failure and permits a successful retry

### a20.1.3 rejects mismatched or private workspace targets before publishing

### a20.1.4 rejects targets excluded from the workspace before publishing

### a20.1.5 requires the requested version in the registry before creating a github release

## a20.2 shared action release plans

### a20.2.1 writes pending matrices to github outputs

### a20.2.2 keeps incomplete pypi releases pending even when their github release exists

## a20.4 recovering PyPI publication

### a20.4.1 retries a partial upload before creating its github release

### a20.4.2 stops before building or creating a release when pypi metadata is invalid
