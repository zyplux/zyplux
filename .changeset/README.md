# Reviewed releases

Each releasable feature includes its prepared versions and changelog entries in the feature PR. Merging to `main` publishes pending versions with those entries on GitHub.

## Write and prepare notes

Run `pnpm change`, select the affected release targets and choose patch for fixes, minor for compatible features or major for breaking changes. Write a short summary describing the effect on consumers; pnpm adds its list marker. Include migration steps when required; give targets separate fragments when their descriptions differ.

```sh
pnpm release:prepare
pnpm release:check
./just c
```

Preparation runs `pnpm version -r`, consumes fragments, updates versions, changelogs and `.changeset/ledger.yaml`, synchronizes Python versions through uv and refreshes both lockfiles. Review and commit these edits with the feature. Private dependent workspaces can receive version bumps; only targets declared in `release-targets.toml` are published.

Zyplux's preparation script also regenerates the resolved ESLint rules snapshot with the current package version.

Python targets have a private `package.json` beside `pyproject.toml` for pnpm discovery. Preparation maintains the mirrored versions; checks require them to agree. Publishing reads the native Python manifest.

GitHub Actions use `kind = "action"` with their GitHub `repository`, versioned `tag_prefix` and floating `major_tag_prefix` in `release-targets.toml`. Their `package.json` provides pnpm discovery; use `private: true` for actions without an npm package. The release workflow creates the fixed versioned GitHub release and updates the corresponding major tag to the newest published stable version in that major. Only versioned tags have GitHub releases; retries also repair the floating tag. Include both the action entrypoint and its implementation in the release surface.

If preparation needs regeneration, preserve the code and note text, restore generated release files to the current `main` baseline, recreate the fragments and rerun `pnpm release:prepare` after any preceding release publishes.

## Shared commands

`@zyplux/release` provides `prepare`, `check`, `notes`, `plan` and publication commands through the shared [release app and action](../apps/release/README.md); CZ's existing commands delegate to it. The notes command emits `kind`, `label`, `version`, `tag` and `notes` for each declared target, without registry access.

Checks reject pending fragments, mismatched Python versions and missing or empty changelog entries. Cerberus separately enforces version bumps for changed release surfaces. GitHub publication uses the exact prepared entry for each target version.
