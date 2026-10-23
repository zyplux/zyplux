# @zyplux/airlock

## 1.0.0

### Major Changes

- Prepare reviewed versions and changelogs with native pnpm and publish npm packages in dependency order with registry availability checks.

- Plan isolated publication batches with separate environments through the Airlock CLI and GitHub Action, including cached workspace setup and custom container artifacts.

- Configure named targets in `airlock-targets.toml` with a shared package scope, optional label overrides and derived versioned and major tags.

- Resume partial PyPI releases through uv and require both a wheel and source archive before marking publication complete.
