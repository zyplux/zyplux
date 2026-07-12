# clipy

Personal typer-based CLI tools that totchef installs from this local checkout — never published to PyPI.

- `ctop` — live top-like CPU view of the VS Code process trees.
- `justpty` — runs a `just` recipe under a PTY, teeing output to a per-run log; this repo's own `./just` is a symlink to it.

## Usage

```bash
uv run ctop [--interval SECONDS] [--once] [--profile-exthost]
uv run justpty [JUST_ARGS...]
```

Each tool is also a self-contained PEP 723 script (see its own `# /// script` header), so it can be copied
anywhere and run standalone via `uv run --script` without this workspace — that's how totchef's
`[local_bin_dir]` recipe entry installs it to `~/.local/bin`: it auto-discovers every script in this
directory meeting the version contract (embeds `__version__`, offers `--version`/`--help`), so a new tool
dropped in here lands on PATH on the next `totchef up` with no recipe edit.
