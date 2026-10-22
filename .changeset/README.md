# Reviewed releases

Each releasable feature includes its prepared versions and changelog entries in the feature PR. Merging to `main` publishes pending versions with those entries on GitHub.

## Write and prepare notes

Run `pnpm run change`, select the affected release targets and choose patch for fixes, minor for compatible features or major for breaking changes. Write short bullets describing the effect on consumers. Include migration steps when required; give targets separate fragments when their descriptions differ.

```sh
pnpm release:prepare
pnpm release:check
./just c
```

Preparation consumes fragments, updates versions and changelogs, synchronizes Python versions through uv and refreshes both lockfiles. Review and commit these edits with the feature. Private dependent workspaces can receive version bumps; only targets declared in `release-targets.toml` are published.

Zyplux's preparation script also regenerates the resolved ESLint rules snapshot with the current package version.

Python targets have a private `package.json` beside `pyproject.toml` for Changesets discovery. Preparation maintains the mirrored versions; checks require them to agree. Publishing reads the native Python manifest.

Prepare once for the complete PR. With no pending fragments, preparation fails; use `release:check` to validate an already prepared release. Additional fragments calculate another bump from the branch's current versions.

When integrating a newer `main`, preserve the feature and release-note text, restore this PR's generated release edits to the new `main` baseline, then recreate its fragments and prepare again. Preserve existing release history and dependency changes.

## Shared commands

CZ provides `prepare-release`, `check-release-notes` and `list-prepared-releases`. The JSON command emits `kind`, `label`, `version`, `tag` and `notes` for each declared target, without registry access. It gives other repository publishers the same version-specific notes and validation.

Checks reject pending fragments, mismatched Python versions and missing or empty changelog entries. Cerberus separately enforces version bumps for changed release surfaces. GitHub publication uses the exact prepared entry for each target version.
