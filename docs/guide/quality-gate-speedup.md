# Quality-gate speedup: a case study

How `just c` went from 61s to ~32s (July 2026), written up as a teaching doc.
The specific numbers will drift; the method and the reasoning are the part
worth keeping.

## Step 0 — profile before optimizing

`just c` is a pipeline of ~15 commands. Before touching anything, each one was
run separately wrapped in `time`, producing a cost map:

| Step                      | Time     | Verdict                 |
| ------------------------- | -------- | ----------------------- |
| vitest (JS tests)         | 24.3s    | worth attacking         |
| pytest (Python tests)     | 15.7s    | worth attacking         |
| cerberus                  | 2.7–6.5s | suspicious variance     |
| eslint                    | 3.5s     | already cached, fine    |
| everything else, combined | ~3s      | ignore                  |

90% of the time lived in 3 of 15 steps; effort on the other 12 would have been
wasted. This table alone decided the whole project.

`time` prints **real** (wall-clock) and **user** (CPU actually burned).
Comparing them tells you *what kind* of slow you have:

- cerberus: 6.5s real, 1.0s user → not computing, **waiting** — almost always
  network or disk.
- vitest: 24s real, 120s user → already parallel across ~5 cores; the fix must
  reduce *work*, not add parallelism.

## Change 1 — `isolate: false` in vitest (24s → 15s)

**What.** By default vitest gives every test *file* a brand-new, sealed
JavaScript environment. Nothing leaks between files — but every file also
re-imports everything from scratch.

**How it was found.** Two experiments. Running with coverage off saved only
~3s, acquitting the initial suspect. The vitest summary line pointed at the
real culprit: `import 70s, transform 17s` — more time loading modules than
running tests. Timing each test project separately showed
`tests/eslint-config` was 18.3s of the 21s: its 15 test files each import the
entire ESLint config stack (typescript-eslint, unicorn, react, perfectionist),
a huge module graph rebuilt 15 times.

**Why the fix helps.** `isolate: false` lets a worker keep its loaded modules
and run several test files in them — the config stack loads once per worker
instead of once per file.

**Accepted tradeoff.** Test files can now see state a previous file left
behind (a mutated global, a leftover mock). `restoreMocks`, `unstubEnvs`, and
`unstubGlobals` mitigate this. If a test ever fails in the full run but passes
alone, suspect this setting first.

## Change 2 — pytest-xdist (16s → 9s)

**What.** Plain pytest runs 605 tests one at a time on one core of an 8-core
machine. `pytest-xdist` with `-n auto` spawns one worker per core.

**How it was found.** `pytest --durations=10` listed the slowest tests: the
totchef story tests take ~1.5s *each* (real subprocess/filesystem work).
Serial slow tests + idle cores = the textbook xdist case. Verified with
`uv run --with pytest-xdist pytest -n auto` — a way to trial a package without
adding it — before committing it to `pyproject.toml`.

**Why it's safe here.** Parallel tests only break when tests share state (same
temp dir, same port, same global). These use isolated `tmp_path` fixtures.
Coverage still works — pytest-cov merges the workers' data.

## Change 3 — parallel gate structure

**What.** Two structural moves in the justfile:

- The `test` recipe starts vitest and pytest **at the same time** and waits
  for both. They're independent, so the 15s job and the 9s job cost
  max(15, 9) instead of 15 + 9.
- `uv run cerberus --fix` moved from `lint` to its own `cerberus` recipe,
  which runs **last** in `check` — after tests.

**Why the cerberus move matters beyond speed.** It fixed a latent correctness
bug. The fallow bite computes a CRAP score (complexity × untested-ness) from
the coverage report tests write — but `lint` ran *before* `test`, so cerberus
always judged the code against the *previous* run's coverage. CLAUDE.md even
carried a warning telling humans how to work around the resulting phantom
findings. Reordering made the warning obsolete: right data, right order, no
ritual.

**The first design was wrong, instructively.** The original attempt built two
fully parallel chains (all JS steps ∥ all Python steps). It was fast — and
then the gate itself failed it: cerberus enforces that every org repo's
justfile has `check`'s steps as ordered dependencies and matches the canonical
`baseline.just` byte-for-byte. Instead of fighting the invariant, the question
became: *where does parallelism actually pay?* Only in `test` — everything
else is ~7s combined. Parallelizing just the tests fits the existing
invariants and lands within a second or two of the fancy version. When you
find yourself fighting a tool, the tool is usually encoding a decision someone
made on purpose.

**Bonus bug found while testing.** `just t <name>` (filtered tests) had been
silently broken *before* these changes: a filtered run covers little code, the
coverage `fail_under 90` check fails, pytest exits 1, and the recipe's
tolerance for exit code 5 never matched. Fix: filtered runs skip coverage
entirely (`--no-cov` / `--coverage.enabled=false`) — which also means a
partial run can no longer overwrite the full coverage report cerberus reads.
Found by simply running `just t nomatchxyz` to verify the rewrite — always
exercise the paths you touched, not just the happy one.

## Change 4 — caching cerberus's registry lookups (~3–6s of network wait)

**What.** The `zyplux_deps_latest` bite asks npm/PyPI/GHCR "what's the latest
version?" over the network on *every* run — answers that change maybe weekly.
The result now lives in `~/.cache/cerberus/registry_latest.json` for an hour.

**How it was found.** The real ≫ user gap from step 0 said "waiting on I/O";
reading the bite's source confirmed HTTP calls to three registries.

**The footgun the design avoids.** A naive one-hour cache fails nastily: run
`just upgrade`, the lockfile now has 0.7.0, but the cache still says "latest
is 0.6.0" — and the check *fails you for being ahead*, telling you to run the
upgrade you just ran. So the rule became: **a cache entry may only confirm a
pass, never justify a fail.** If the cached latest matches what's in use →
trust it, skip the network. Any disagreement → look up live. The only blind
spot left is inherent to any TTL: a release published minutes ago goes
unnoticed for up to an hour, locally only (CI runners start with no cache).

Deliberately *not* cached: `release_surface_version_bump`, the bite that gates
releases — a stale answer there could corrupt a release decision; freshness is
the point.

**Process.** Test-first, per this repo's convention: behavior spec as story
section 22.6, four tests, three failing, then implementation until green. And
because `baseline.just` and the bite code are part of cerberus's published
release surface, another bite demanded the version bump to 0.14.0 — the
governance machine policing its own change.

## Takeaways

1. **Profile before optimizing** — 3 of 15 steps held 90% of the time.
2. **real vs user time** tells you whether you're compute-bound (do less work)
   or wait-bound (cache, parallelize, or reorder).
3. **Parallelize only independent long poles** — concurrency everywhere buys
   little over concurrency where it counts, and costs structure.
4. **Order operations by data flow** — the producer of data (tests →
   coverage) must run before its consumer (cerberus).
5. **Caches need a story for staleness** — decide who may be lied to, for how
   long, and make the cache unable to cause false alarms.
6. **When the tooling pushes back, listen** — the rejected first design is why
   the final one is both fast and idiomatic.
