# @zyplux/cz

Repo automation for `zyp-cerberus`, exposed as the `cz` CLI.

## Usage

```text
cz push [-r|--ready]    Push the current branch and open or advance its draft PR.
cz clone <repo> [ref]   Shallow-clone a reference repo into reference_clones/.
cz release              Publish any bumped release target via a GitHub release.
cz bootstrap <LABEL>    First-publish a new npm target with a token (then enable trusted publishing).
cz apply-ruleset        Upsert every org ruleset in .github/rulesets/ (needs org-admin gh auth).
```

Run it from the workspace root:

```text
bun run cz <command>
```

Or through `just`:

```text
just push
just clone <repo> [ref]
just release
just apply-org-ruleset
```
