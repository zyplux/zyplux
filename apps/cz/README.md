# @zyplux/cz

Repo automation, exposed as the `cz` CLI. Requires [Bun](https://bun.sh).

## Install

Run without installing:

```bash
bunx @zyplux/cz <command>
```

Or install globally for the `cz` command:

```bash
bun add -g @zyplux/cz
cz <command>
```

## Usage

```bash
cz push-branch [-r|--ready]             Push the current branch and open or advance its draft PR.
cz clone-reference-repo <repo> [ref]    Shallow-clone a reference repo into reference_clones/.
cz release-bumped-targets               Publish any bumped release target via a GitHub release.
cz bootstrap-npm-target <LABEL>         First-publish a new npm target with a token (then enable trusted publishing).
cz deps-catalog [--dir DIR] [--out FILE] Resolve every dependency across the repos to its source repo; write catalog.json.
cz clean [--dry-run] [--exclude DIR...] Remove gitignored build artifacts/caches from this repo, or every repo under the cwd.
cz test [NAME]                          Run JS (bun run test) and Python (uv run pytest) tests in parallel; NAME filters by test name, skipping coverage.
```

## License

MIT
