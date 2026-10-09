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
cz bootstrap-npm-target <LABEL>         First-publish using local npm authentication, then enable trusted publishing.
cz deps-catalog [--dir DIR] [--out FILE] Resolve every dependency across the repos to its source repo; write catalog.json.
cz clean [--dry-run] [--exclude DIR...] Remove gitignored build artifacts/caches from this repo, or every repo under the cwd.
cz lint-mermaid                       Check Mermaid diagrams in tracked and unignored Markdown under the current Git directory.
cz upgrade [--interactive] [PACKAGE...] Upgrade the pinned toolchain plus JavaScript and Python workspace dependencies.
```

## License

MIT
