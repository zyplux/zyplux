# @zyplux/airlock

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
