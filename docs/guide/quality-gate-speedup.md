# Quality-gate speedup: a case study

How `just c` went from 61s to ~32s (July 2026). The numbers will drift; the method and reasoning are the part worth keeping.

## Step 0 — profile before optimizing

`just c` is a pipeline of ~15 commands. Each was run separately wrapped in `time`, producing a cost map:

| Step                      | Time     | Verdict              |
| ------------------------- | -------- | -------------------- |
| vitest (JS tests)         | 24.3s    | worth attacking      |
| pytest (Python tests)     | 15.7s    | worth attacking      |
| cerberus                  | 2.7–6.5s | suspicious variance  |
| eslint                    | 3.5s     | already cached, fine |
| everything else, combined | ~3s      | ignore               |

90% of the time lived in 3 of 15 steps; effort on the other 12 would have been wasted. This table alone decided the whole project.

`time` prints **real** (wall-clock) and **user** (CPU actually burned). Comparing them tells you *what kind* of slow you have:

- cerberus: 6.5s real, 1.0s user → not computing, **waiting** — almost always network or disk.
- vitest: 24s real, 120s user → already parallel across ~5 cores; the fix must reduce *work*, not add parallelism.

## Change 1 — `isolate: false` in vitest (24s → 15s)

By default vitest gives every test *file* a brand-new, sealed JavaScript environment. Nothing leaks between files — but every file re-imports everything from scratch.

Coverage-off saved only ~3s, acquitting the initial suspect. The vitest summary line named the real culprit: `import 70s, transform 17s` — more time loading modules than running tests. Per-project timing pinned it on `tests/eslint-config` (18.3s of 21s): its 15 files each import the entire ESLint config stack (typescript-eslint, unicorn, react, perfectionist), a huge module graph rebuilt 15 times.

`isolate: false` lets a worker keep its loaded modules across test files — the config stack loads once per worker instead of once per file.

**Accepted tradeoff.** Files can now see state a previous file left behind (a mutated global, a leftover mock). `restoreMocks`, `unstubEnvs`, and `unstubGlobals` mitigate this. If a test fails in the full run but passes alone, suspect this setting first.

## Change 2 — pytest-xdist (16s → 9s)

Plain pytest runs 605 tests serially on one core of an 8-core machine. `pytest --durations=10` showed the totchef story tests take ~1.5s *each* (real subprocess/filesystem work). Serial slow tests + idle cores is the textbook case for `pytest-xdist -n auto`: one worker per core. Verified with `uv run --with pytest-xdist pytest -n auto` — a way to trial a package without adding it — before committing it to `pyproject.toml`.

It's safe here because parallel tests only break when they share state (a temp dir, a port, a global), and these use isolated `tmp_path` fixtures. Coverage still works — pytest-cov merges the workers' data.

## Change 3 — parallel gate structure

Two structural moves in the justfile:

- The `test` recipe starts vitest and pytest **at the same time** and waits for both: max(15, 9) instead of 15 + 9. (The runner logic later moved into `cz test`, so every org repo gets it from one place.)
- `uv run cerberus --fix` moved from `lint` to its own `cerberus` recipe, running **last** in `check` — after tests.

The cerberus move fixed a latent correctness bug, not just speed: the fallow bite computes a CRAP score (complexity × untested-ness) from the coverage report tests write — but `lint` ran *before* `test`, so cerberus always judged code against the *previous* run's coverage. CLAUDE.md even carried a warning about the resulting phantom findings. Right order made the warning obsolete.

**The first design was wrong, instructively.** Two fully parallel chains (all JS steps ∥ all Python steps) were fast — and the gate itself failed them: cerberus requires `check`'s steps as ordered dependencies matching the canonical baseline. Instead of fighting the invariant, ask: *where does parallelism actually pay?* Only in `test` — everything else is ~7s combined. Parallelizing just the tests fits the invariants and lands within a second or two of the fancy version. When you find yourself fighting a tool, it's usually encoding a decision someone made on purpose.

**Bonus bug found while testing.** `just t <name>` (filtered tests) had been broken all along: a filtered run covers little code, coverage `fail_under 90` fails, pytest exits 1 — never the tolerated 5. Fix: filtered runs skip coverage (`--no-cov` / `--coverage.enabled=false`), which also stops partial runs from clobbering the coverage report cerberus reads. Found by running `just t nomatchxyz` — always exercise the paths you touched, not just the happy one.

## Rejected — caching cerberus's registry lookups (~3–6s of network wait)

The `zyplux_deps_latest` bite asks npm/PyPI/GHCR "what's the latest version?" on *every* run. A one-hour TTL cache under `~/.cache/cerberus/` was built, passed the gate — and was reverted.

The bite's entire job is to enforce that consumers are on the latest release *immediately* — the org workflow is release, then bump consumers right away. A TTL cache means the check silently stops enforcing exactly when it matters most, for up to an hour. Against that: ~3 seconds saved. Enforcement tools earn their keep by being trustworthy; trading trust for seconds is a bad deal, and every cache adds a state file, an invalidation story, and a new way to be confused by a stale run. A cache is only acceptable where staleness is harmless — in a *linter for freshness*, staleness is the one intolerable thing.

**Kept instead: concurrency, not caching.** Fresh answers, fetched in parallel. `zyplux_deps_latest` already fanned its lookups out over a thread pool; `release_surface_version_bump` got the same treatment — prefetch all targets concurrently, verify sequentially from the prefetched map, findings byte-identical. Batching was also checked: neither npm nor PyPI offers a multi-package endpoint; GHCR's auth token can cover several repositories in one request (repeated `scope=` params), worth doing only if the org ever consumes more than one GHCR image per run — today each bite queries exactly one.

**Version note.** `baseline.just` and the justfile bite changed (change 3) — a release-surface change, so the release-surface bite demanded a cerberus version bump: the governance machine policing its own change.

## Takeaways

1. **Profile before optimizing** — 3 of 15 steps held 90% of the time.
2. **real vs user time** tells you whether you're compute-bound (do less work) or wait-bound (cache, parallelize, or reorder).
3. **Parallelize only independent long poles** — concurrency everywhere buys little over concurrency where it counts, and costs structure.
4. **Order operations by data flow** — the producer (tests → coverage) must run before its consumer (cerberus).
5. **Never cache what a tool exists to keep fresh** — a staleness window in a freshness check hollows out the check; seconds saved don't buy back lost trust.
6. **When the tooling pushes back, listen** — the rejected first design is why the final one is both fast and idiomatic.
