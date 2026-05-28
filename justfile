# Dev recipe applied by `just up`/`plan`/`lint`; override with `just up recipe=path`.
recipe := "examples/recipe.toml"

up:
    uv run totchef up --recipe {{recipe}}

plan:
    uv run totchef plan --recipe {{recipe}}

cooks:
    uv run totchef --list-cooks

deadcode:
    uvx vulture

lint: deadcode
    ruff check --fix
    ruff format
    rumdl check --fix
    uv run python tests/project/story_links.py
    uv run totchef lint --recipe {{recipe}}

tc: lint
    uvx pyright

# Run tests. With no selector, run the whole suite (after typecheck). A selector
# targets story tests by their numeric id — dots/underscores optional, matched as a
# prefix: `just test 1.1.1` / `111` / `1_1_1` → the 1.1.1 story; `just test 2` → all
# of story 2; `just test 42` → every test under 4.2.
test selector="": tc
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -z "{{selector}}" ]; then
        uv run pytest
    else
        digits="$(printf '%s' '{{selector}}' | tr -d '._')"
        pattern="test_$(printf '%s' "$digits" | sed 's/./&_/g')"
        uv run pytest tests/stories -k "$pattern" --no-cov
    fi

# Shallow-clone a repo (owner/name or URL) into reference_clones/; optional ref keeps history back to but excluding that commit/tag (e.g. just clone microsoft/vscode 1.121.0)
clone repo ref="":
    scripts/clone_reference.py {{repo}} {{ref}}
