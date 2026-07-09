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

# Install both workspaces: bun + uv.
install:
    bun install
    uv sync --all-packages --all-groups

# Report unused files, deps, and exports: knip (JS workspace, default + prod pass) + vulture (Python).
knip:
    bun run knip
    bun run knip --config knip.prod.json
    uv run vulture

# Type-check both workspaces: tsc/bun for .ts, pyrefly for .py.
typecheck:
    bun run typecheck
    uv run pyrefly check

# Lint and format both workspaces with autofix.
lint:
    bun run lint:fix
    bun run format
    uv run rumdl check --fix
    uv run rumdl fmt
    uv run ruff check --fix
    uv run ruff format

# Run tests for both workspaces, JS and Python in parallel. Optional arg filters by test name, skipping coverage; never fails when nothing matches.
test name='':
    #!/usr/bin/env bash
    set -euo pipefail
    js_log=$(mktemp) py_log=$(mktemp)
    trap 'rm -f "$js_log" "$py_log"' EXIT
    bun run test {{ if name == '' { '' } else { '-t ' + quote(name) + ' --passWithNoTests --coverage.enabled=false' } }} >"$js_log" 2>&1 &
    js_pid=$!
    (uv run pytest {{ if name == '' { '' } else { '--no-cov -k ' + quote(name) } }} || [ "$?" -eq 5 ]) >"$py_log" 2>&1 &
    py_pid=$!
    js_status=0 py_status=0
    wait "$js_pid" || js_status=$?
    wait "$py_pid" || py_status=$?
    cat "$js_log" "$py_log"
    [ "$js_status" -eq 0 ] && [ "$py_status" -eq 0 ]

# Verify org invariants with cerberus, over the coverage report `test` regenerates.
cerberus:
    uv run cerberus --fix

# Full gate across both workspaces: install, knip, typecheck, lint, test, cerberus — autofix throughout.
check: install knip typecheck lint test cerberus

# Upgrade deps across both workspaces: ncu bumps JS ranges; uv lock --upgrade + uv-bump raise Python >= floors. Forwards extra args to ncu.
upgrade *args='':
    bun run upgrade -- {{ args }}
    uv lock --upgrade
    uvx uv-bump -v
    uv sync --all-packages --all-groups

# Interactively select JS upgrades, then non-interactively upgrade Python (uv has no interactive mode) and reinstall both.
upgrade-interactive:
    bun run upgrade -- -i
    bun install
    uv lock --upgrade
    uvx uv-bump -v
    uv sync --all-packages --all-groups

# Push the current branch and open a draft PR (-r/--ready marks it ready and enables auto-merge).
push *flags:
    bun run cz push-branch {{ flags }}

# Push the current branch and open a PR marked ready, enabling auto-merge.
push-ready: (push "--ready")

# Remove gitignored build artifacts and caches from all workspaces.
clean *flags:
    bun run cz clean {{ flags }}
