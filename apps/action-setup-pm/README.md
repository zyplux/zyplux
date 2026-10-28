# Set up package managers

The [shared action](action.yml) prepares pnpm and uv workspaces on GitHub-hosted Linux runners. Check out the consuming repository before calling it.

```yaml
- uses: actions/checkout@v7
- uses: zyplux/zyplux/apps/action-setup-pm@setup-pm-v1
```

`setup-pm-v1` points to the latest published compatible action release. pnpm prepares the action's version and changelog; the release workflow creates a fixed `setup-pm-v1.0.0` release with those notes, then updates the matching major tag. Retries repair missing tags and retain the newest published version in that major. Breaking changes get a new major tag. Zyplux uses `./apps/action-setup-pm` in its own workflows to test the checked-out action.

The action requires root `package.json`, `pyproject.toml`, `pnpm-lock.yaml` and `uv.lock` files. pnpm requires a plain `pnpm@<version>` pin of 11.1.0 or newer in `packageManager` and an exact Node.js version in `devEngines.runtime`. uv defaults to `0.13.4`, configurable through `uv-version`, and selects Python through the repository's `.python-version` or project requirements.

Executable cache keys include the version, operating system and architecture. Node.js and uv use their upstream setup actions. A cold pnpm install uses the official standalone installer with `PNPM_VERSION` set to the workspace pin; pnpm 12 downloads are verified against npm registry signatures and checksums. Shell configuration is written to runner temporary storage. pnpm's store and metadata cache share a lockfile key with a version-specific fallback. uv hashes the exact root lockfile and Python version file. GitHub scopes caches to the consuming repository and permitted branches.

By default, each call restores pnpm's dependency cache and runs `pnpm install --frozen-lockfile --no-runtime` and `uv sync --locked --all-packages --all-groups`. Set `install-dependencies: 'false'` to prepare only the cached tools.

Publication jobs populate the main-branch caches that subsequent PRs can restore. PR caches are isolated to their merge ref.
