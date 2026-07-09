# CLAUDE.md

## Leading the Pack

This is the org's reference repo for quality: it sets the bar the other zyplux repos are measured against, and they look here for how things should be done. Every new strict check ships here first — this repo dogfoods it (see `cerberus.toml`, which tightens the org-wide duplication threshold to a flat 0) before it rolls out org-wide via a cerberus release. Hold changes to that standard: when a check bites, raise the code to meet it rather than the other way around.

## Quality Gate

Run `just c` to apply auto-fixes and verify the change. It is the full gate across both the bun (JS/TS) and uv (Python) workspaces — install, knip, typecheck, lint + format, tests (JS and Python in parallel), then cerberus verifying org invariants over the fresh coverage — with autofix throughout. Run it before considering a change done; it must pass clean.

The `fallow_analyzer` bite reads the istanbul coverage report, which only the full `bun run test` regenerates (`just t <name>`-filtered runs skip coverage entirely). `just c` always runs the full tests before cerberus; a standalone `uv run cerberus` after source changes may read stale coverage and report phantom complexity findings — run the full `bun run test` first.

## Justfile BASELINE Region

The justfile's `# BASELINE` region is owned by `apps/cerberus/src/cerberus/baseline.just` (cerberus is installed editable, so that file IS the packaged canonical). To change a baseline recipe, edit `baseline.just` and run `just c` — `cerberus --fix` rewrites this repo's justfile from it immediately; other org repos pick the change up after a cerberus release, once their bumped `cerberus --fix` runs. Never edit the justfile's BASELINE region directly: the next `just c` silently reverts it.
