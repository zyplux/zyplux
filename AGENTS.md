# AGENTS.md

## Leading the Pack

This is the org's reference repo for quality: it sets the bar the other zyplux repos are measured against, and they look here for how things should be done. Every new strict check ships here first — this repo dogfoods it (see `cerberus.toml`, which tightens the org-wide duplication threshold to a flat 0) before it rolls out org-wide via a cerberus release. Hold changes to that standard: when a check bites, raise the code to meet it rather than the other way around.

## Quality Gate

Run `just c` to apply auto-fixes and verify the change. It is the full gate across both the pnpm (JS/TS) and uv (Python) workspaces — install, knip, typecheck, lint + format, tests (JavaScript, then Python), then cerberus verifying org invariants over the fresh coverage — with autofix throughout. Run it before considering a change done; it must pass clean.

The `fallow` bite reads the istanbul coverage report, which only the full `pnpm run test` regenerates. `just c` always runs the full tests before cerberus; a standalone `uv run cerberus` after source changes may read stale coverage and report phantom complexity findings — run the full `pnpm run test` first.

## Running `just` Recipes

Use the `./just` wrapper (not bare `just`) — it runs the recipe under a PTY and streams an ANSI-free transcript to a per-run file `logs/just-<timestamp>-<pid>.log`, announced on stderr as `» log: …`; `logs/just.log` is a symlink to the latest run, and only the newest 20 run logs are kept. Recipes like `just c` are slow, so launch with Bash's `run_in_background: true` then grep the run's log path; safe to grep even mid-run; each log opens with `=== <start time> | <command>` ends with `=== exit <status> | <end time> | <duration>`
