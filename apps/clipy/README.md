# clipy

Shared Python CLI helpers, published as `zyplux-clipy`. [CZ](../cz/README.md) provides the repository-facing commands; Clipy supplies their Python reporting and orchestration. Cerberus supplies source classification, and Airlock prepares releases.

```sh
uv add --dev zyplux-clipy
uv run clipy stats [PATH] [--out FILE] [--title TITLE]
uv run clipy fingerprint [PATH]
```

`fingerprint` prepares release metadata, invokes `pnpm exec cz workspace-graph`, writes code statistics, then lets Airlock calculate release fingerprints. Install both CZ and Clipy in the consuming repository's pnpm and uv workspaces.

## Terminal tools

- `ctop` — live CPU view of VS Code process trees.
- `justpty` — runs a `just` recipe under a PTY and saves a transcript; this repo's `./just` uses it.

```sh
uv run ctop [--interval SECONDS] [--once] [--profile-exthost]
uv run justpty [JUST_ARGS...]
```

These two tools are also self-contained PEP 723 scripts. Totchef's `local_bin_dir` cook installs scripts carrying a version and offering `--version`/`--help` from this checkout into `~/.local/bin`.
