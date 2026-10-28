# AGENTS.md

## Leading the Pack

This is the org's reference repo for quality: it sets the bar the other zyplux repos are measured against, and they look here for how things should be done. Every new strict check ships here first — this repo dogfoods it (see [`cerberus.toml`][1], which tightens the org-wide duplication threshold to a flat 0) before it rolls out org-wide via a cerberus release. Hold changes to that standard: when a check bites, raise the code to meet it rather than the other way around.

Follow the [Airlock release workflow][2] when preparing or publishing releases.

## Quality Gate

Run `./just lint typecheck` locally. Run targeted tests when needed; leave full-suite testing and Cerberus to CI. Use `./just c` locally only when explicitly requested. The full CI gate must pass clean before merging.

The local [`./just` logging wrapper][3] is a convenience tool maintained through linting and typechecking. Its [implementation][4] is intentionally outside automated tests and coverage.

Version-bump detection is a best-effort reminder. Fix clear bugs while favoring simple checks over support for unused edge cases.

The [source oracle][5] classifies prod, infra, demo, test and docs. Its [configured `needs_tests` flag][6] controls other test-presence bites.

The [`fallow` bite][7] reads the istanbul coverage report, which only the full `pnpm run test` regenerates. `just c` always runs the full tests before cerberus; a standalone `uv run cerberus` after source changes may read stale coverage and report phantom complexity findings — run the full `pnpm run test` first.

## Running `just` Recipes

Use the [`./just` wrapper][3] (not bare `just`) — it runs the recipe under a PTY and streams an ANSI-free transcript to a per-run file `logs/just-<timestamp>-<pid>.log`, announced on stderr as `» log: …`; `logs/just.log` is a symlink to the latest run, and only the newest 20 run logs are kept. Recipes like `just c` are slow, so launch with Bash's `run_in_background: true` then grep the run's log path; safe to grep even mid-run; each log opens with `=== <start time> | <command>` ends with `=== exit <status> | <end time> | <duration>`

[1]: cerberus.toml
[2]: apps/airlock/README.md
[3]: just
[4]: apps/clipy/src/clipy/justpty.py
[5]: apps/cerberus/src/cerberus/source_oracle.py
[6]: apps/cerberus/src/cerberus/cerberus.toml
[7]: apps/cerberus/src/cerberus/bites/fallow_bite.py
