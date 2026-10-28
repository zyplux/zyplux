# clipy

Python CLI helpers for repository metrics and terminal tools, published as `zyplux-clipy`.

```sh
uv add --dev zyplux-clipy
uv run clipy stats [PATH] [--out FILE] [--title TITLE]
```

## Terminal tools

- `ctop` — live CPU view of VS Code process trees.
- `justpty` — runs a `just` recipe under a PTY and saves a transcript; this repo's `./just` uses it.

```sh
uv run ctop [--interval SECONDS] [--once] [--profile-exthost]
uv run justpty [JUST_ARGS...]
```

`ctop` and `justpty` also run as self-contained PEP 723 scripts.
