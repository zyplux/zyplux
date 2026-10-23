# Airlock

Prepare reviewed versions and changelogs with pnpm's versioning engine, publish npm packages with native pnpm, and publish Python packages, containers and GitHub Actions through `release-targets.toml`.

```sh
pnpm change
pnpm release:prepare
pnpm release:check
```

Preparation runs `pnpm version -r`; pnpm owns dependency propagation, versions, changelogs and the consumed-intent ledger. Set `versioning.changelog.storage: repository` in `pnpm-workspace.yaml` to review generated notes in the feature PR.

Preparation supplies each npm scope's `publishConfig` registry to pnpm for version lookups. Targets in one scope must share a publication registry, and private registries need configured pnpm credentials.

The `airlock` CLI provides `prepare`, `check`, `notes`, `plan`, `publish-npm` and `publish --release TAG`.

## GitHub Action

Add `@zyplux/airlock` as a locked development dependency. After checkout and package-manager setup, use the action in the repository's publishing job:

```yaml
- uses: zyplux/zyplux/apps/action-airlock@airlock-v1
  with:
    command: publish-npm
```

The action uses the installed CLI. `plan` exposes `npm`, `pypi`, `ghcr` and `action` outputs as JSON tag arrays. `publish` requires a `tag`; `check` validates prepared notes. Triggers, job permissions, registry credentials, trusted-publishing environments and concurrency belong to the calling workflow. Zyplux's release workflow dogfoods `./apps/action-airlock`.

Npm publication filters the declared npm targets, publishes in dependency order, saves `pnpm-publish-summary.json` and waits for registry metadata and tarball accessibility. Retrying also creates missing GitHub releases for versions uploaded by an earlier attempt. Package `prepack` hooks perform builds and archive validation.

All kinds share preparation and reviewed changelogs. Python packages use private pnpm tracking manifests synchronized with `pyproject.toml` through uv. PyPI publication requires both a wheel and source archive; uv builds into an isolated directory and retries incomplete uploads before creating the GitHub release.

## Custom container artifacts

Repositories with a custom image builder run it before the action. Build and push the versioned image, then supply its generated deployment manifest as a release asset:

```yaml
- uses: zyplux/zyplux/apps/action-airlock@airlock-v1
  with:
    command: publish
    tag: core-v0.4.2
    assets: release.json
```

The target's versioned image must already exist. The app validates notes and local assets, uploads assets to a draft GitHub release, and publishes it after upload succeeds. Retries resume drafts; a published release missing required assets fails validation.

## Publication

The app publishes to npm as `@zyplux/airlock`; its action publishes fixed `airlock-vX.Y.Z` tags and advances the compatible `airlock-vX` alias. `airlock-cli-vX.Y.Z` identifies the npm package release.

The initial npm package requires the existing bootstrap workflow and trusted-publisher configuration. Subsequent versions publish automatically after merge.
