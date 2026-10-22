# @zyplux/cz

Repo automation, exposed as the `cz` CLI. Requires [Node](https://nodejs.org) 26 and [pnpm](https://pnpm.io).

## Install

Run without installing:

```bash
pnpx @zyplux/cz <command>
```

Or install globally for the `cz` command:

```bash
pnpm add -g @zyplux/cz
cz <command>
```

## Usage

```bash
cz push-branch [-r|--ready]             Push the current branch and open or advance its draft PR.
cz clone-reference-repo <repo> [ref]    Shallow-clone a reference repo into reference_clones/.
cz release-bumped-targets               Publish any bumped release target via a GitHub release.
cz release-bumped-targets --list [--tag TAG] Print pending artifact kinds and tags as JSON.
cz publish-tagged-target [--release] TAG Publish one artifact; optionally create its GitHub release after publication.
cz prepare-release                    Prepare Changesets versions, changelogs and lockfiles, synchronizing Python versions.
cz check-release-notes                Validate prepared versions and non-empty changelog entries.
cz list-prepared-releases             Print validated kind, label, version, tag and notes records as JSON.
cz bootstrap-npm-target <LABEL>         First-publish using local registry authentication.
cz deps-catalog [--dir DIR] [--out FILE] Resolve every dependency across the repos to its source repo; write catalog.json.
cz clean [--dry-run] [--exclude DIR...] Remove gitignored build artifacts/caches from this repo, or every repo under the cwd.
cz lint-mermaid                       Check Mermaid diagrams in tracked and unignored Markdown under the current Git directory.
cz upgrade [--interactive] [PACKAGE...] Upgrade the pinned toolchain plus JavaScript and Python workspace dependencies.
```

Npm targets use their package's `publishConfig` registry and access settings. A matching `@scope:registry` takes precedence over `registry`; either URL may end with a slash. Supported registries are npmjs and GitHub Packages. GitHub package lookups require `NODE_AUTH_TOKEN`; publishing uses npm's registry authentication configuration.

`--list` selects configured versions missing either their registry artifact or GitHub release, and prints `[]` when every release is complete. It reads the current checkout without requiring a local `main` branch. `--release` records the checked-out commit after successful publication; retries preserve existing artifacts and complete missing release metadata.

Release creation uses the current target version's `CHANGELOG.md` entry. Preparation and note checks use `.changeset` and `release-targets.toml`; see the [release workflow](../../.changeset/README.md). Python targets need a private `package.json` with their native name and version beside `pyproject.toml`. Preparation requires uv for Python targets. The JSON command checks notes and mirrored versions without accessing registries and provides the shared interface for other publishers.

## License

MIT
