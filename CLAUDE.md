# CLAUDE.md

## Quality Gate

Run `just c` to apply auto-fixes and verify the change. It is the full gate
across both the bun (JS/TS) and uv (Python) workspaces — install, knip,
typecheck, lint + format, tests (JS and Python in parallel), then cerberus
verifying org invariants over the fresh coverage — with autofix throughout.
Run it before considering a change done; it must pass clean.

The `fallow_analyzer` bite reads the istanbul coverage report, which only
the full `bun run test` regenerates (`just t <name>`-filtered runs skip
coverage entirely). `just c` always runs the full tests before cerberus; a
standalone `uv run cerberus` after source changes may read stale coverage
and report phantom complexity findings — run the full `bun run test` first.
