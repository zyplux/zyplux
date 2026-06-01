set shell := ["bash", "-euo", "pipefail", "-c"]

alias l := lint
alias tc := typecheck
alias t := test
alias i := install
alias u := upgrade
alias ui := upgrade-interactive
alias c := check

# List available recipes.
default:
    @just --list

# Install dependencies (the prepare script installs git hooks via lefthook).
install:
    bun install

# Upgrade JS dependencies across the workspace via ncu (catalog-aware). Forwards extra args (e.g. `just u -i`).
upgrade *args='':
    bun run upgrade -- {{ args }}

# Interactively select and apply upgrades, then reinstall.
upgrade-interactive:
    bun run upgrade -- -i
    bun install

# Report unused files, dependencies, and exports via knip.
knip:
    bun run knip

# Auto-format with prettier.
format:
    bun run format

# Type-check root config files and all workspaces; runs knip first.
typecheck: knip
    bun run typecheck

# Lint (eslint) — autofix by default; runs typecheck first. --check/-c to check only.
[arg('fix', long='check', short='c', value='')]
lint fix='--fix': typecheck
    bun run {{ if fix == '--fix' { 'lint:fix' } else { 'lint' } }}

# Run all workspace tests; runs lint first. --check/-c to skip lint fixes.
[arg('fix', long='check', short='c', value='')]
test fix='--fix': (lint fix)
    bun run test

# Verify like CI (no autofix): knip, type-check, lint, format check, test.
check:
    bun run knip
    bun run typecheck
    bun run lint
    bunx prettier --check .
    bun run test

# Cut a GitHub release for the current package version, then watch the publish workflow and verify it on npm.
release:
    bun run release

# Remove dependencies and caches.
clean:
    rm -rf node_modules packages/*/node_modules tests/*/node_modules
