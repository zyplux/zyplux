# Set up package managers

The [shared action](../../setup-pm/action.yml) prepares pnpm and uv workspaces on GitHub-hosted Linux runners. Check out the consuming repository before calling it.

```yaml
- uses: actions/checkout@v7
- uses: zyplux/zyplux/setup-pm@v1
```

`v1` points to the latest published compatible action release. Changesets prepares the action's version and changelog; the release workflow creates a fixed `setup-pm-v1.0.0` release with those notes, then updates the matching major tag. Retries repair missing tags and retain the newest published version in that major. Breaking changes get a new major tag. Zyplux uses `./setup-pm` in its own workflows to test the checked-out action.

The action requires root `package.json`, `pyproject.toml`, `pnpm-lock.yaml` and `uv.lock` files. pnpm requires a plain `pnpm@<version>` pin of 11.1.0 or newer in `packageManager` and an exact Node.js version in `devEngines.runtime`. uv defaults to `0.13.4`, configurable through `uv-version`, and selects Python through the repository's `.python-version` or project requirements.

Executables are cached by version, operating system and architecture independently of dependency lockfiles. Node.js and uv use their upstream setup actions. A cold pnpm install uses the official standalone installer with `PNPM_VERSION` set to the workspace pin; pnpm 12 downloads are verified against npm registry signatures and checksums. Warm runs restore the installed executable without running the installer. Shell configuration is written to runner temporary storage. pnpm's store and metadata cache share a lockfile key with a version-specific fallback. uv hashes the exact root lockfile and Python version file. GitHub scopes caches to the consuming repository and permitted branches.

Every call runs `pnpm install --frozen-lockfile --no-runtime` and `uv sync --locked --all-packages --all-groups`. Cerberus requires checkout and the shared action before checks in the unconditional CI job, and rejects standalone toolchain setup actions in workflows.

Zyplux's main-branch release selector runs both toolchains to populate caches that subsequent PRs can restore. PR caches are isolated to their merge ref.

The preflight script uses the runner's Python 3.12 or newer and has no third-party dependencies.
