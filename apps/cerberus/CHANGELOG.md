# zyplux-cerberus

## 0.25.1

### Patch Changes

- Delegate release-surface validation to the repository-installed Airlock CLI; publishing repositories must install `@zyplux/airlock` as a root development dependency.

- Require the newest stable tool versions eligible under pnpm's 24-hour release quarantine, keeping freshness checks consistent with installation policy.

- Require the shared package-manager action at `zyplux/zyplux/apps/action-setup-pm`.

- Read version-bump and publication targets from `airlock-targets.toml`; migrate to named target tables with a top-level `scope` before upgrading.

## 0.25.0

### Minor Changes

- Require version bumps when a GitHub Action's release surface changes, using its published GitHub releases as the baseline.

## 0.24.0

### Minor Changes

- Require checkout and the shared setup-pm action before checks in the unconditional CI job, and reject standalone toolchain setup actions in workflows.

## 0.23.2

### Patch Changes

- Allow repairs to unpublished release versions while preventing version regressions and changes to published versions without a bump.
- Require pnpm/setup@v3 for pnpm setup and recognize its frozen installs in the CI check sequence.
- Run duplication checks with jscpd 5.4.2.

## 0.23.1

### Patch Changes

- Verify pnpm lockfiles and avoid requiring approval for Copilot workflow runs.
