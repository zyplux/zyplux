# zyplux-cerberus

## 0.26.1

### Patch Changes

- Require Airlock 2.1 for consistent container build-input fingerprints.

- Run Fallow 3.36.0 for source and coverage analysis.

## 0.26.0

### Minor Changes

- Validate prepared release metadata and content fingerprints through `release_readiness`, reusing Airlock's publishing validators. Local gates and CI run this through Cerberus.

- Detect changes to package archives and Action/container inputs against fingerprints in finalized release tags, without downloading published artifacts. Release targets declare fingerprints rather than manual file lists.

- Implement release-surface validation in Cerberus using its own findings and reusing Airlock's manifest and registry helpers. Publishing repositories no longer need an Airlock npm dependency or Node subprocess for this check.

### Patch Changes

- Fetch finalized GitHub release history once for all release targets.

- Reuse Cerberus's cached repository access for release manifests, version files and Git history so targets sharing a baseline file read it once per run.

- Run Fallow 3.35.0 for source and coverage analysis.

- Use Airlock's registry client for dependency and tool-pin freshness, sharing authentication and response validation with release checks while preserving npm's minimum release age.

## 0.25.2

### Patch Changes

- Reuse the existing GitHub CLI login for private npm and container registry reads when explicit credentials are absent; preserve CI token precedence and report access failures.

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
