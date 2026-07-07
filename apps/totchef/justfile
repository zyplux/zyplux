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

# Install both workspaces: bun + uv.
install:
    bun install
    uv sync --all-groups

# Report unused files, deps, and exports: knip (JS workspace) + vulture (Python).
knip:
    bun run knip
    uv run --group lint vulture

# Type-check both workspaces: tsc/bun for .ts, pyrefly for .py.
typecheck:
    bun run typecheck
    uv run --group typecheck pyrefly check

# Lint and format both workspaces with autofix: eslint + prettier, then ruff, story links, rumdl, and recipe lint via totchef.
lint:
    bun run lint:fix
    bun run format
    uv run --group lint ruff check --fix
    uv run --group lint ruff format
    uv run python tests/project/sync_story_links.py
    uv run --group lint rumdl check --fix
    uv run totchef lint --recipe {{ recipe }}

# Run tests for both workspaces. Optional arg filters by test name; never fails when nothing matches.
test name='':
    bun run test {{ if name == '' { '' } else { '-t "' + name + '" --passWithNoTests' } }}
    uv run pytest {{ if name == '' { '' } else { '-k "' + name + '"' } }} || [ "$?" -eq 5 ]

# Full gate across both workspaces: install, knip, typecheck, lint, test — autofix throughout.
check: install knip typecheck lint test

# Upgrade deps across both workspaces: ncu bumps JS ranges; uv lock --upgrade + uv-bump raise Python >= floors. Forwards extra args to ncu.
upgrade *args='':
    bun run upgrade -- {{ args }}
    uv lock --upgrade
    uvx uv-bump -v
    uv sync --all-groups

# Interactively select JS upgrades, then non-interactively upgrade Python (uv has no interactive mode) and reinstall both.
upgrade-interactive:
    bun run upgrade -- -i
    bun install
    uv lock --upgrade
    uvx uv-bump -v
    uv sync --all-groups

# Push the current branch and open a draft PR (-r/--ready marks it ready and enables auto-merge).
push *flags:
    bun run cz push-branch {{ flags }}

# Push the current branch and open a PR marked ready, enabling auto-merge.
push-ready: (push "--ready")

# Remove deps and caches from all workspaces.
clean:
    rm -rf node_modules packages/*/node_modules apps/*/node_modules tests/*/node_modules
    rm -rf .venv .pytest_cache .ruff_cache .rumdl_cache .eslintcache .tsbuild
    find . -type d \( -name __pycache__ -o -name .tsbuild -o -name dist -o -name .ruff_cache -o -name .pytest_cache \) -prune -exec rm -rf {} +
    find . -type f \( -name '*.tsbuildinfo' -o -name '.eslintcache' -o -name '*.py[cod]' \) -delete

# Shallow-clone a repo (owner/name or URL) into reference_clones/; optional ref keeps history back to but excluding that commit/tag (e.g. just clone microsoft/vscode 1.121.0)
clone repo ref="":
    scripts/clone_reference.py {{ repo }} {{ ref }}

# CUSTOM

# Dev recipe applied by `just up`/`plan`/`lint`; override with `just up recipe=path`.
recipe := "examples/totchef_recipe.toml"

# Build the standalone binary, then apply the recipe (so [file.totchef] installs the freshly-built totchef).
up: build
    uv run totchef up --recipe {{ recipe }}

# Dry-run: show what `up` would change without applying.
plan:
    uv run totchef plan --recipe {{ recipe }}

# List available cooks.
cooks:
    uv run totchef --list-cooks

# Build the standalone single-file totchef binary into the recipe's totchef_files/ (installed by [file.totchef] so `totchef up` runs from anywhere). Re-run after code changes.
build:
    uv run --with pyinstaller pyinstaller --onefile --name totchef --collect-submodules totchef.cooks --copy-metadata totchef --distpath examples/totchef_files --workpath build/pyinstaller --specpath build/pyinstaller src/totchef/__main__.py
