# BASELINE
set shell := ["bash", "-euo", "pipefail", "-c"]

alias i := install
alias k := knip
alias tc := typecheck
alias l := lint
alias t := test
alias c := check
alias u := upgrade
alias ui := upgrade-interactive
alias p := push
alias pr := push-ready

# List available recipes.
default:
    @just --list

# Install both workspaces: pnpm + uv.
install:
    pnpm install
    uv sync --all-packages --all-groups

# Report unused files, deps, and exports: knip (JS workspace, default + prod pass) + vulture (Python).
knip:
    pnpm run knip
    pnpm run knip --config knip.prod.json
    uv run vulture

# Type-check both workspaces: tsc for .ts, pyrefly for .py.
typecheck:
    pnpm run typecheck
    uv run pyrefly check

# Lint and format both workspaces with autofix.
lint:
    pnpm run lint:fix
    pnpm run format
    uv run rumdl check --fix
    uv run rumdl fmt
    uv run ruff check --fix
    uv run ruff format

# Run available JavaScript tests, then Python tests; pytest exit code 5 means no tests were collected.
test:
    test -f package.json || test -f pyproject.toml
    if test -f package.json; then pnpm run test; fi
    if test -f pyproject.toml; then uv run pytest || test "$?" -eq 5; fi

# Verify org invariants with cerberus, over the coverage report `test` regenerates.
cerberus:
    uv run cerberus --fix

# Full gate across both workspaces: install, knip, typecheck, lint, test, cerberus — autofix throughout.
check: install knip typecheck lint test cerberus

# Upgrade the pinned toolchain plus JavaScript and Python workspace dependencies through cz.
upgrade *args='':
    pnpm run --silent cz upgrade {{ args }}

# Interactively select toolchain and JavaScript upgrades; Python upgrades remain non-interactive.
upgrade-interactive:
    @pnpm run --silent cz upgrade --interactive

# Push the current branch and open a draft PR (-r/--ready marks it ready and enables auto-merge).
push *flags:
    pnpm run cz push-branch {{ flags }}

# Push the current branch and open a PR marked ready, enabling auto-merge.
push-ready: (push "--ready")

# Remove gitignored build artifacts and caches from all workspaces.
clean *flags:
    pnpm run cz clean {{ flags }}

# CUSTOM

alias d := dump-rules

# Shallow-clone a reference repo into reference_clones/ (optional branch or tag).
clone repo ref="":
    pnpm run cz clone-reference-repo {{ repo }} {{ ref }}

# Dump the fully-resolved ESLint config (all rules) to packages/eslint-config/rules.json.
dump-rules:
    pnpm run --filter @zyplux/eslint-config dump-rules

# Apply totchef's own dogfood recipe to this machine.
totchef:
    uv run totchef up --recipe apps/totchef/examples/totchef_recipe.toml

# Publish any bumped release target (eslint-config → npm, cerberus → PyPI, ci image → GHCR) via GitHub releases.
release:
    pnpm run --silent cz release-bumped-targets
