# cerberus

The repository guard and shared source classifier. Verifies invariants for zyplux repository checkouts — CI workflow structure, justfile and dependency conventions, CODEOWNERS, and release-version bumps.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) and Python 3.14

The `justfile` bite shells out to `just`, which ships with the package (via [`rust-just`](https://pypi.org/project/rust-just/)) — no separate install. The `jscpd` and `fallow` bites run their tools via `pnpx` at exact versions pinned in [`tool_pins.py`](src/cerberus/tool_pins.py), so every cerberus release measures with the same tools everywhere; `pnpm` must be on PATH.

Source checks use tracked and unignored files: TypeScript checks require `.ts`, `.tsx`, `.mts` or `.cts` files, and Python checks require `.py` or `.pyi` files. Executable TypeScript tool configuration counts as source. Manifests used only to install tooling do not require application lint, typecheck or test steps. Ruff, Knip, Pyrefly and pytest configuration stays optional without source; supplied configuration must satisfy the same invariants. Package metadata, dependency, CI and Markdown checks still apply.

CI uses one unquoted canonical command with literal arguments per `run` step. Python tool calls use `uv run --no-sync`; Prettier uses `pnpm exec prettier --check`.

Tooling-only repositories carry a Python tooling manifest and run Rumdl for Markdown. Prettier is required only when TypeScript source is present.

Release targets record their content fingerprints in `airlock-targets.toml`. The `release_surface_version_bump` bite implements the version-bump policy, including repairs to unpublished versions and `GITHUB_BASE_REF` comparisons. The `release_readiness` bite validates consumed change intents, synchronized Python versions, current release notes and content fingerprints. Both checks reuse release helpers from the `zyplux-airlock` Python dependency. Release-history reads use `gh auth login` locally or `GH_TOKEN` in CI. Fetch complete Git history and the target branch before running the check.

Dependency freshness and tool-pin freshness share Airlock's registry client for npm, PyPI and GHCR. Tool-pin lookups select stable npm versions within the `latest` release line that satisfy the configured minimum release age. Lookup failures produce error findings.

Named target tables derive their tag prefix as `<name>-v` and their label as `<scope>/<name>` from the manifest's top-level `scope`; an explicit `label` overrides the default. Action targets use `kind = "action"` and a GitHub `repository`. Their latest published stable version comes from GitHub releases matching the derived tag prefix, across all pages. Action fingerprints cover the action directory and its version-file directory; set `path` when those differ. Floating major tags do not define the version baseline.

## Lint a repo

```sh
uv run cerberus            # lint the current directory
uv run cerberus PATH       # lint a checkout at PATH
```

Runs every bite and exits non-zero on any failure or error, so it drops into CI like any linter. Run `cerberus list` to see every bite, its scope, and what it verifies.

| Option           | Description                                                       |
| ---------------- | ----------------------------------------------------------------- |
| `--check NAME`   | Limit to named bite(s); repeatable                                |
| `--config PATH`  | Overlay file applied in place of the repo root `cerberus.toml`    |
| `--fix`          | Auto-fix fixable problems (e.g. trailing whitespace)              |
| `--verbose`/`-v` | Itemize what each bite measured (clones, dead-code issues)        |

A repo switches a bite off with `off = true` in that bite's `cerberus.toml` table (see Config below); naming an off bite with `--check` still runs it.

## Bites

| ID                             | Scope       | Verifies                                                                            |
| ------------------------------ | ----------- | ----------------------------------------------------------------------------------- |
| `source_oracle`             | content     | Category globs and shared policies enforce unambiguous classification and allowed nesting |
| `justfile`                     | content     | Recipe names, aliases, ordered `check` dependencies and body calls, local cerberus run, wrapped tool calls, no trailing whitespace |
| `ci_workflow_gate`             | content     | `ci.yml` exists, exposes a `ci` check, runs on PRs (push to `main` recommended)      |
| `ci_check_sequence`            | content     | `ci.yml` uses shared package-manager setup before the canonical checks             |
| `ci_cerberus_step`             | content     | A CI workflow runs cerberus to self-verify org invariants                           |
| `workflow_toolchain_only`      | content     | Workflows use shared package-manager setup and install no extra tools              |
| `pyrefly`                      | content     | All code, tests included, type-checks under strict pyrefly with no relaxations       |
| `ruff`                         | content     | ruff runs standalone in preview with `select = ["ALL"]`; relaxations stay sanctioned |
| `line_length`                  | content     | ruff `line-length` and prettier `printWidth` both match the configured width (120)   |
| `rumdl`                        | content     | `.rumdl.toml` carries the org-canonical rule config (per-repo `exclude` allowed)    |
| `knip`                         | content     | knip config is standalone, never inline in `package.json`; `knip.prod.json` runs the entry-exports pass and exempts exactly the repo's published npm targets |
| `vitest`                       | content     | TypeScript tests use Vitest |
| `tsc`                          | content     | TypeScript typecheck runs via project references (`tsc -b`) |
| `catalog_pinned_deps`          | content     | Every workspace `package.json` dependency pins via `catalog:` or `workspace:`        |
| `vitest_coverage` | content | Root Vitest coverage thresholds meet the configured floor |
| `consistent_package_export_entries` | content | Workspace packages use index roots or named modules, with matching source/publication keys; application router roots match their TanStack Vite entry |
| `explicit_module_side_effects` | content | Library packages declare `false` or module patterns that preserve detected initialization in source and published modules |
| `consistent_workspace_project_references` | content | Workspace TypeScript projects reference their compiled dependencies once |
| `no_worker_filesystem_imports` | content | First-party Worker runtime imports avoid filesystem builtins |
| `pnpm_release_age` | content | pnpm waits one day before installing new third-party releases; only `@zyplux/*` packages may be exempt |
| `story_tests_lockstep_py`      | content     | `tests/**/stories/**/*.md` criteria have a matching, title-matched pytest test          |
| `story_tests_lockstep_ts`      | content     | Each TypeScript story directory pairs numeric or prefixed criterion IDs with tests          |
| `cli_py_test_seam`             | content     | CLI apps' story tests import only their root module or cli entry module              |
| `lib_py_test_seam`             | content     | Libraries' story tests import only their root module                                |
| `release_readiness` | content | Change intents are consumed, Python versions match, release notes exist and fingerprints match current contents |
| `release_surface_version_bump` | git-history | A published target's version is bumped by exactly one step whenever its release contents change |
| `codeowners_coverage`          | content     | `CODEOWNERS` present and covers `/.github/`                                          |
| `pytest` | content | pytest configuration enforces a coverage floor of at least 90% |
| `jscpd`                        | content     | Copy-paste duplication per language stays under the configured jscpd threshold      |
| `fallow`                       | content     | fallow finds no unused code, circular imports, or functions above its complexity thresholds |
| `zyplux_deps_latest`           | content     | Every `@zyplux/*` npm package, `zyplux-*` PyPI distribution, and `ghcr.io/zyplux` image is used at its latest release |
| `tool_pins_latest`             | content     | Npm tool pins are the newest stable releases eligible under pnpm's one-day quarantine |

## Justfile recipes

[`baseline.just`](src/cerberus/baseline.just) is the starting template. Cerberus checks names, aliases, ordered gate steps and their actual tool calls, managed-tool runners, cleanup, and whitespace. Required calls run as standalone foreground commands that preserve failures; local shell helpers start with `set -euo pipefail` and contain no other `set` commands. Local Cerberus commands start with `uv run cerberus`. The test recipe may guard runners by their workspace manifests and accept pytest's empty-suite exit code. Application recipes may add parameters, modules, and commands; `--fix` removes trailing whitespace.

## Fallow inputs

`[fallow].entry_points` registers exact repository files loaded by framework or runtime conventions that Fallow cannot infer. Every declared file must exist. CRAP is enabled by default: `[fallow].coverage_report` defaults to `coverage/coverage-final.json` and must exist; run tests before Cerberus to refresh it.

`[fallow.rules]` accepts [Fallow rule names](https://fallow.tools/docs/configuration/rules/). Set `complexity-crap = "off"` to disable CRAP and its coverage-file requirement while retaining dead-code and source complexity checks. Other rules can be disabled individually. Rules not overridden retain Fallow's defaults; Cerberus's `--fail-on-issues` makes both `error` and `warn` findings fail.

## Config

Every default lives in [`cerberus.toml`](src/cerberus/cerberus.toml), under its bite's table (`[source_oracle]`, `[justfile]`, `[pytest]`, …). The bundled file is the single home of the defaults; missing required keys are errors. A repo adjusts them with a root `cerberus.toml`, overlaid key by key. An explicit `--config PATH` stands in for that repository file. Lists replace the corresponding default list.

Every bite table also takes a common `off` key, handled by the runner: `off = true` removes the bite from the run entirely — no output line — and an overlay's `off = false` re-enables a bite the bundled defaults ship off. `tool_pins_latest` ships off for exactly that reason: only the repo carrying the pin source can act on it, and that repo's overlay switches it on.

### Shared source classification

`source_oracle` is the single classifier used by repository checks and reports. Each category defines `roots`, `needs_tests` and `allowed_child_types` in the bundled defaults:

| Category | Purpose | Needs tests | Allowed child categories |
| --- | --- | --- | --- |
| `prod` | Shipped applications and libraries | Yes | All |
| `infra` | Repository, CI and deployment code | Yes | All |
| `demo` | Examples and demonstrations | No | None |
| `test` | Tests, fixtures and coverage reporting | No | test, demo, docs |
| `docs` | Documentation, including embedded executable code | No | None |

Consumer overlays replace category globs; policies remain shared. For example:

```toml
[source_oracle.types.prod]
roots = ["apps/*", "packages/*", "src", "tools/*"]

[source_oracle.types.demo]
roots = ["demo", "examples", "infra/demo"]
```

Root globs are repository-relative paths. Deeper matches win; equally deep matches use the most literal pattern. Equally specific conflicting categories fail. `allowed_child_types` names the categories permitted **inside** a category. Demo and docs roots are terminal; their contents retain that category. Unmatched paths are infra. Colocated tests retain their enclosing category and have an independent `is_test` flag, derived from `[source_oracle].test_files`.

Existing test-presence checks use `needs_tests`. Repositories configure test discovery, runners and coverage. `[source_oracle].test_exempt_files` records explicit repository policy exceptions. Linting and strict typechecking cover every category.

Knip uses prod classification and registered TypeScript workspaces; `uv run cerberus --check knip --fix` regenerates `ignoreWorkspaces`. Pyrefly requires `min-severity = "warn"`; `extends` and command-line severity overrides are rejected.

Python callers use `load_source_oracle(repo_root).classify(relative_path)` from `cerberus`; the result contains `kind`, `root`, `is_test` and `needs_tests`. Classification is pure; callers discover files.

`zyplux_deps_latest` queries npm, PyPI, and GHCR at lint time; a failed lookup is reported as an error, never a silent pass. It has no `--fix` — run `just upgrade` to catch up.

`tool_pins_latest` requires the newest stable jscpd/fallow versions eligible under pnpm's one-day release quarantine. It runs only in the repo carrying `tool_pins.py`; consumers receive updated pins through Cerberus releases.

## Package and source checks

TypeScript seam checks use ESLint's resolved imports. Focused export, ownership and reference checks enforce package policies.

Worker traversal covers first-party static imports and literal dynamic imports. Normal output summarizes static coverage limits; `--verbose` lists computed imports, third-party modules, and framework-provided entries that require production bundle validation.

Side-effect detection checks registration and initialization in workspace source modules against package-relative `sideEffects` paths. Packages publishing compiled files use patterns that also cover their compiled modules. The check cannot prove an arbitrary dependency graph pure.

Vitest coverage resolves exported literal objects and local constants, including `defineConfig` and its direct-return callbacks, without executing configuration code. Every metric meets the configured floor, and collection is enabled through `test.coverage.enabled: true` or the root test script's coverage flag.
