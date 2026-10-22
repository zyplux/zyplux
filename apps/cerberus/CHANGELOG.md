# zyplux-cerberus

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
