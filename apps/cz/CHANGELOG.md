# @zyplux/cz

## 0.16.1

### Patch Changes

- Refresh packaged dependency metadata for the updated workspace toolchain.

- Updated dependencies:
  - @zyplux/util@0.9.4

## 0.16.0

### Minor Changes

- Add workspace dependency diagrams, balanced file chunking and repository statistics through Clipy.

## 0.15.0

### Minor Changes

- Use the standalone `@zyplux/airlock` CLI for release commands: replace `cz <release-command>` with `airlock <release-command>`.

## 0.14.1

### Patch Changes

- Wait for newly published GitHub Actions to appear in GitHub's release list before advancing their major tags, avoiding failed publications caused by briefly stale API responses.

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
