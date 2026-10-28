# zyplux-airlock

## 2.2.0

### Minor Changes

- Consolidate repeated release preparation into one pending release and restore release metadata after preparation failures.

### Patch Changes

- Allow release preparation to replay after formatting the intent ledger.

## 2.1.1

### Patch Changes

- Reuse GitHub login for private package registry lookups during release preparation while preserving configured pnpm credentials.

## 2.1.0

### Minor Changes

- Use Dockerfile-adjacent ignore files consistently for container builds and build-input fingerprints. Include all admitted context files, including Git-ignored inputs, and identify selected paths on fingerprint mismatches. Regenerate container fingerprints after upgrading.

- Require container ignore files to exclude `.git` so fingerprints remain stable across commits and checkouts.

## 2.0.0

### Major Changes

- Publish Airlock as the `zyplux-airlock` Python distribution. Cerberus reuses its manifest and registry helpers, and the Airlock action runs its own locked implementation. Remove the `@zyplux/airlock` npm dependency from consumers and use `uv run airlock` for local release commands; select `action-airlock-v2` for the Python action.

- Use `prepare`, `plan` and `publish` for releases. Cerberus reports release readiness through its `release_readiness` bite. Preparation records release-content fingerprints for every target. Publication runs one target per batch, and planning installs only the Python publisher runtime. Cerberus owns version-bump enforcement.

- Record release fingerprints in `airlock-targets.toml`: normalized npm/Python archives, Action source directories and container build inputs filtered by build ignore rules. Verify fingerprints during checks and publication.

- Share npm, PyPI and GHCR metadata lookups with Cerberus, including credential discovery and minimum-age npm version selection.

## 1.1.1

### Patch Changes

- Reuse the existing GitHub CLI login for private npm and container registry reads when explicit credentials are absent; preserve CI token precedence and report access failures.

## 1.1.0

### Minor Changes

- Publish GHCR targets from declared Dockerfiles and build contexts, add OCI version and revision labels, and attach release.json manifests containing the version and digest-pinned image.

### Patch Changes

- Pack each npm target once in its publication job, inspect packing hooks' final manifest, wait for retained workspace dependency versions and tarballs, and upload the inspected archive. Packing failures leave unrelated releases running.

- Publish each npm package in its own job so a failed package does not block other releases or their GitHub changelog entries.

## 1.0.0

### Major Changes

- Enforce release-surface version bumps through a shared CLI check with structured findings for Cerberus and direct use.

- Prepare reviewed versions and changelogs with native pnpm and publish npm packages in dependency order with workspace validation and registry availability checks.

- Plan isolated publication batches with separate environments through the Airlock CLI and GitHub Action, including cached workspace setup, custom container artifacts and image-only builders. Finalized container releases require their versioned image and declared assets.

- Configure named targets in `airlock-targets.toml` with a shared package scope, optional label overrides and derived versioned and major tags.

- Resume partial PyPI releases through uv and require both a wheel and source archive before marking publication complete.
