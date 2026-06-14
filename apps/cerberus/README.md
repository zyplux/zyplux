# cerberus

A CLI that verifies org-wide repository invariants across the zyplux organization — CI workflows, branch-protection rulesets, CODEOWNERS, workflow secrets, and justfile conventions. It reads every repo in the org through the GitHub CLI and reports each one against a policy.

## Requirements

- [`gh`](https://cli.github.com/), authenticated against the org (`gh auth login`)
- [`uv`](https://docs.astral.sh/uv/) and Python 3.14
- [`just`](https://just.systems/) (the `justfile` check shells out to it)

## Use

```sh
uv run cerberus repos        # list the repos cerberus governs
uv run cerberus scorecard    # cross-repo pass/fail matrix
uv run cerberus verify       # every finding, per repo
```

Options (`scorecard` and `verify`):

| Option          | Description                                  |
| --------------- | -------------------------------------------- |
| `--config PATH` | Use a `cerberus.toml` other than the bundled |
| `--repo`, `-r`  | Limit to named repo(s)                       |
| `--check`, `-k` | Limit to named check(s)                      |
| `--json`        | Emit JSON instead of a table                 |
| `--strict`      | Treat warnings as failures                   |

A non-passing result (failure, or any warning under `--strict`) exits non-zero.

## Checks

| ID                 | Verifies                                             |
| ------------------ | ---------------------------------------------------- |
| `justfile`         | Uniform recipe names, aliases, and `check` pipeline  |
| `ci-workflow`      | `ci.yml` exists, exposes a `ci` check, runs on PRs   |
| `ruleset`          | Default branch protected by the org baseline ruleset |
| `workflow-secrets` | Every secret referenced in workflows is provisioned  |
| `codeowners`       | `CODEOWNERS` present and covers `/.github/`          |

## Config

Policy — org name, excluded repos, ruleset name, required recipes and aliases — lives in [`cerberus.toml`](src/cerberus/cerberus.toml). Override it with `--config PATH`.
