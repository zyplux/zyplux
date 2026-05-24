up:
    ./src/chef.py

_prime-sudo:
    sudo -v

lint:
    ruff check --fix
    ruff format

tc: lint
    uvx pyright src

clone repo:
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{repo}}" in
        http*://* | git@*) url="{{repo}}" ;;
        *) url="https://github.com/{{repo}}.git" ;;
    esac
    name="$(basename "{{repo}}" .git)"
    dest="reference_clones/$name"
    [ -e "$dest" ] && { echo "$dest already exists — remove it first: rm -rf $dest" >&2; exit 1; }
    git clone --depth 1 --single-branch "$url" "$dest"
    echo "Cloned $url -> $dest (shallow, single-branch). Delete with: rm -rf $dest"
