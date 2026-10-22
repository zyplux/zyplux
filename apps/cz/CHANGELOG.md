# @zyplux/cz

## 0.14.0

### Minor Changes

- Publish GitHub Actions through prepared Changesets releases, and keep major tags on the newest compatible published version with retry-safe updates.

## 0.13.0

### Minor Changes

- Publish npm artifacts with pnpm’s native publisher so trusted publishing uses the pinned toolchain.

- Prepare reviewed changelogs with Changesets and publish each target's notes on its GitHub release. Share release preparation, validation and JSON metadata through CZ, including Python version synchronization.

### Patch Changes

- Check npm package metadata for unpublished versions when selecting and publishing releases.
- Updated dependencies
  - @zyplux/util@0.9.3

## 0.12.0

### Minor Changes

- Publish pending package versions automatically on pushes to main, with per-target retries for missing artifacts and GitHub releases.
