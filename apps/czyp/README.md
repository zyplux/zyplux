# czyp

Repo automation, exposed as the `czyp` CLI. Requires [Bun](https://bun.sh).

## Install

Run without installing:

```bash
bunx czyp <command>
```

Or install globally for the `czyp` command:

```bash
bun add -g czyp
czyp <command>
```

## Usage

```bash
czyp push-branch [-r|--ready]             Push the current branch and open or advance its draft PR.
czyp clone-reference-repo <repo> [ref]    Shallow-clone a reference repo into reference_clones/.
czyp release-bumped-targets               Publish any bumped release target via a GitHub release.
czyp bootstrap-npm-target <LABEL>         First-publish a new npm target with a token (then enable trusted publishing).
czyp apply-org-rulesets                   Upsert every org ruleset in .github/rulesets/ (needs org-admin gh auth).
```

## License

MIT
