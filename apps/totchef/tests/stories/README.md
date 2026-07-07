# stories

The numbered `<n>_<section>.md` docs describe `totchef` strictly from the **user's
point of view** — what someone running `totchef` (or authoring a recipe, or extending
it) can do and observe. The two roles referenced throughout:

- **Operator** — the person who owns a machine, writes its `recipe.toml`, and runs
  `totchef` to converge it.
- **Cook author** — a developer who extends `totchef` with a new domain (a "cook")
  via a plugin or a local file.

End-to-end, prose-style tests over fixtures. A test names the fixtures it needs and
reads like the user story it covers. Each one drives the whole stack — recipe parse,
dependency graph, cook probe/act, the chef's diff, and the real report rendering —
with only the system boundaries faked: bash, network, and the home directory.

That makes them behavior tests, not unit tests: a green test means the real pipeline
works for that scenario. For isolated, fast checks of pure logic (parsers, the graph
builder, schema validation), see the unit tests alongside.

## Source of truth — one direction only

The story docs are the source of truth for these tests; the tests are the source of
truth for production code. The arrow never points back:

- **Stories know nothing about tests.** A story describes user-facing behavior. **Never
  edit a story to make it easier to test** — if a criterion is hard to assert, that is a
  fact about the test harness, not a reason to weaken the story. Either find a way to
  observe the real behavior (e.g. the `apply_in_container` fixture for the privilege
  drop) or leave the story as-is and note the gap.
- **Tests chase stories.** If a test asserts something the story doesn't claim — or
  something internal — then either it isn't testing the story, or the story is wrong;
  fix the test (or the story, *as a deliberate spec change*, never to fit a test).
- **Production chases tests.** Code exists to make the behavior the tests assert true.

## Prefer full-snapshot assertions

Where a command's output is deterministic, assert the **whole thing** at once
(`CliResult.assert_output`, `RunReport.assert_report`) rather than picking at it row by
row. A full snapshot reads as exactly what the software returns, so a reviewer sees the
real shape and a regression shows up as a clear diff. Fall back to a targeted assertion
(`assert_lists`, `assert_shows`) only when the output carries a run-varying value a
snapshot can't pin — a `local:<path>` origin, a temp path, a timestamp.

## The fixtures

- `recipe` — build the recipe.toml: `recipe.declares("bash", "deep_sleep", apply=...)`
  for a subtable entry, `recipe.declares("apt_pkg", packages=[...])` for a plain
  section.
- `terminal` — the bash boundary (`totchef.shell`). Arrange a command's reply with
  `arrange(match, output, exit_code=0, effect=...)`, verify with `expect_ran(match)` /
  `expect_not_ran(match)`. `match` is a substring of the shell-joined command, and a
  later `arrange` for the same match wins (a probe re-run can see new state). `effect`
  is a successful command's side effect on the world (e.g. an installer dropping a
  binary). Also: `count(match)`, `stdin_for(match)`, `reset()`.
- `http` — the network boundary (`harness.urlopen`). Arrange a URL's body with
  `arrange(url_match, body)`, verify with `expect_fetched(match)`. An un-programmed
  URL raises, so no test reaches the real network.
- `home` — `$HOME` redirected to a temp dir; per-user cooks (`settings`,
  `chromium_flags`, `desktop`) write under it. Returns the Path to read back.
- `system` — the host boundary. PATH is isolated to an empty bin dir, so a cook's
  `find_binary`/`shutil.which` sees only what you provision: `system.has("cargo")`.
  `system.running_release("plucky")` pins the codename apt_repo reads.
- `tmp_path` — pytest's builtin. Point a cook's absolute paths (`file.path`,
  `apt_repo.keyring`/`source_path`) here.
- `totchef` — the user action: `totchef.plan()`, `totchef.up()`, `totchef.lint()`.
  Returns a report with `assert_shows(node, action)`, `assert_logged(snippet)`,
  `assert_report(toon)`, `assert_succeeded()`, `assert_soft_failed()`,
  `assert_hard_failed()`.
- `cli` — invoke a real `totchef <command>` (`where`/`lint`/`--version`/`--list-cooks`)
  and read what it printed: `assert_prints`, `assert_output` (full snapshot),
  `assert_lists` (targeted row), `assert_succeeded`/`assert_failed`.
- `apply_in_container` — run a real `totchef up` inside a throwaway container as a
  non-root user and read back ownership (`run.owners[path]`, `run.log_owner`). For the
  few stories whose criterion is the real privilege drop (§7.3.2, §8.3.1), which the
  in-process suite can't observe. Skips when podman is absent. See `container_fixtures`.

## Arrange, act, check — each line says which it is

- **Arrange** (setup only): `recipe.declares(...)`, `terminal.arrange(...)`,
  `http.arrange(...)`.
- **Act**: `totchef.plan()` / `totchef.up()` / `totchef.lint()`.
- **Check**, always prefixed so it's never mistaken for a query:
  - `expect_…` — what the system *did at a mocked boundary*: `terminal.expect_ran`,
    `terminal.expect_not_ran`, `http.expect_fetched`.
  - `assert_…` (and the `assert` keyword) — *real produced outcome/state*: the
    report's actions, files on disk.

## Shape of a test

```python
def test_up_runs_the_apply_when_state_differs(recipe, terminal, totchef):
    recipe.declares("bash", "deep_sleep",
        current_state="cat /sys/power/mem_sleep", desired_state="deep",
        apply="echo deep > /sys/power/mem_sleep")
    terminal.arrange("cat /sys/power/mem_sleep", "s2idle [deep]")

    report = totchef.up()

    report.assert_shows("bash.deep_sleep", "applied")
    terminal.expect_ran("echo deep > /sys/power/mem_sleep")
```

## Why these are the only mocks

Every cook reaches the outside world through three narrow chokepoints, each patched
at a single place:

- bash → `totchef.shell.run` / `shell.stream` (module-qualified everywhere).
- network → `harness.urlopen` (the one call all `fetch_url`s funnel through).
- home → `$HOME`, which `Path.home()` and `~` resolve from.

Everything else — the chef's diffing, dependency graph, and reporting — runs for
real, in-process: no fork, no sudo. Filesystem writes are real too, just redirected
into `tmp_path` / `home`, so content-hash idempotency is exercised end to end.
