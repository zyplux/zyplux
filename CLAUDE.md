# CLAUDE.md

## Quality Gate

Run `just c` to apply auto-fixes and verify the change. It is the full gate
across both the bun (JS/TS) and uv (Python) workspaces — install, knip,
typecheck, lint + format, and tests — with autofix throughout. Run it before
considering a change done; it must pass clean.
