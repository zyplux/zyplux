set shell := ["bash", "-euo", "pipefail", "-c"]

alias i := install
alias k := knip
alias tc := typecheck
alias l := lint
alias t := test
alias c := check
alias d := dump-rules
alias u := upgrade
alias ui := upgrade-interactive
alias p := push
alias pr := push-ready

# List available recipes.
default:
    @just --list

# Install both workspaces: bun + uv.
install:
    bun install
    uv sync --all-packages --all-groups

# Report unused files, deps, and exports: knip (JS workspace) + vulture (Python).
knip:
    bun run knip
    uv run vulture

# Type-check both workspaces: tsc/bun for .ts, pyrefly for .py.
typecheck:
    bun run typecheck
    uv run pyrefly check

# Lint and format both workspaces with autofix, then verify org invariants with cerberus.
lint:
    bun run lint:fix
    bun run format
    uv run rumdl check --fix
    uv run rumdl fmt
    uv run ruff check --fix
    uv run ruff format
    uv run cerberus --fix

# Run tests for both workspaces. Optional arg filters by test name; never fails when nothing matches.
test name='':
    bun run test {{ if name == '' { '' } else { '-t "' + name + '" --passWithNoTests' } }}
    uv run pytest {{ if name == '' { '' } else { '-k "' + name + '"' } }} || [ "$?" -eq 5 ]

# Full gate across both workspaces: install, knip, typecheck, lint, test — autofix throughout.
check: install knip typecheck lint test

# Upgrade JS dependencies across the workspace via ncu (catalog-aware). Forwards extra args (e.g. `just u -i`).
upgrade *args='':
    bun run upgrade -- {{ args }}

# Interactively select and apply upgrades, then reinstall.
upgrade-interactive:
    bun run upgrade -- -i
    bun install

# Publish any bumped release target (eslint-config → npm, cerberus → PyPI, ci image → GHCR) via GitHub releases.
release:
    bun run czyp release-bumped-targets

# Upsert every org ruleset in .github/rulesets/ to GitHub (source of truth). Needs gh authenticated with org-admin scope.
apply-org-ruleset:
    bun run czyp apply-org-rulesets

# Push the current branch and open a draft PR (-r/--ready marks it ready and enables auto-merge).
push *flags:
    bun run czyp push-branch {{ flags }}

# Push the current branch and open a PR marked ready, enabling auto-merge.
push-ready: (push "--ready")

# Remove dependencies and caches from both workspaces.
clean:
    rm -rf node_modules packages/*/node_modules tests/*/node_modules
    rm -rf .venv .pytest_cache .ruff_cache .rumdl_cache
    find . -type d -name __pycache__ -prune -exec rm -rf {} +

# Shallow-clone a reference repo into reference_clones/ (optional branch or tag).
clone repo ref="":
    bun run czyp clone-reference-repo {{ repo }} {{ ref }}

# Dump the fully-resolved ESLint config (all rules) to packages/eslint-config/rules.json.
dump-rules:
    bun run --cwd packages/eslint-config dump-rules
