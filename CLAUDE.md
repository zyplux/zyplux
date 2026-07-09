# CLAUDE.md

## Quality Gate

Run `just c` to apply auto-fixes and verify the change. It is the full gate
across both the bun (JS/TS) and uv (Python) workspaces — install, knip,
typecheck, lint + format, and tests — with autofix throughout. Run it before
considering a change done; it must pass clean.

The `fallow_analyzer` bite reads the istanbul coverage report, so running a
subset of tests overwrites it and causes phantom complexity findings — run the
full `bun run test` to regenerate coverage, then re-run `just c`.
