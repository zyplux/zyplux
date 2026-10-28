# cerberus

Verifies invariants for zyplux repository checkouts — CI workflow structure, justfile and dependency conventions, CODEOWNERS, and release-version bumps.

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

## Repository reports

```sh
uv run cerberus fingerprint        # prepare versions, reports, then release hashes
uv run cerberus workspace-graph    # WORKSPACE_GRAPH.md
uv run cerberus stats              # line_and_token_stats.md
uv run cerberus stats apps/cerberus --title "Cerberus" --out reports/cerberus.md
```

`fingerprint [PATH]` resolves the Git root and prepares configured release versions, both reports, then release hashes. Without release targets it writes the reports alone. It stops on failure. The root justfile exposes `./just fingerprint`, `./just stats` and `./just dep-graph`; consumers can call the CLI directly.

Stats read tracked files from the current working tree without changing the index. Stage new files before generating a report that includes them. Lockfiles, the stats report and binary content stay outside the tables. Line, syntax and o200k_base token counts use the same source classification as the governance checks. The first tokenizer use may download its encoding. The separate `token_stats` application compares tokenizer performance.

The workspace diagram reads pnpm and uv membership and declared dependencies. Python and TypeScript manifests in one directory form one node. Test harness workspaces are omitted. TypeScript imports determine type-only arrows; frequently imported foundations appear in a separate list. This workspace overview complements the source-level `graph` commands.

## Bites

| ID                             | Scope       | Verifies                                                                            |
| ------------------------------ | ----------- | ----------------------------------------------------------------------------------- |
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
| `vitest`                       | content     | TypeScript tests use Vitest rather than Bun's test runner |
| `tsc`                          | content     | TypeScript typecheck runs via project references (`tsc -b`), not a per-package fan-out |
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
| `pytest` | content | Shared source ownership controls discovery and coverage; the coverage floor remains at least 90% |
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

Every default lives in [`cerberus.toml`](src/cerberus/cerberus.toml): shared source ownership under `[source]`, and check settings under their bite's table (`[justfile]`, `[pytest]`, `[jscpd]`, …). The bundled file is the single home of the defaults; missing required keys are errors. A repo adjusts them with a root `cerberus.toml`, overlaid key by key. An explicit `--config PATH` stands in for that repository file. Lists replace the corresponding default list.

Every bite table also takes a common `off` key, handled by the runner: `off = true` removes the bite from the run entirely — no output line — and an overlay's `off = false` re-enables a bite the bundled defaults ship off. `tool_pins_latest` ships off for exactly that reason: only the repo carrying the pin source can act on it, and that repo's overlay switches it on.

### Shared source ownership

```toml
[source]
production_roots = ["apps/*", "packages/*", "src"]
infrastructure_roots = ["infra"]
tooling_roots = ["tools", "scripts"]
demo_roots = ["infra/demo", "tests/demo"]
test_roots = ["tests", "doubles"]
test_exempt_files = []
test_files = [
    "**/tests/**",
    "**/__tests__/**",
    "**/*.test.*",
    "**/*.spec.*",
    "**/test_*.py",
    "**/*_test.py",
    "**/conftest.py",
]
```

Root patterns are repository-relative directory globs. A deeper matching root wins; at the same depth, the pattern with more literal characters wins. Equally specific conflicting owners are errors. `*` matches one segment and `**` spans directories. Unclassified files are maintained tooling. Test-file patterns identify colocated tests independently of their owner's kind.

Product, infrastructure and tooling source require tests and coverage. Demo source and test support do not. Declare demo suites by their actual directory ownership, as in `tests/demo`; a product test using a demo fixture retains its ownership. `test_exempt_files` records explicit repository policy exceptions, such as Zyplux's local logging wrapper.

Knip intersects product ownership with registered TypeScript workspaces; a standalone root package remains production. `uv run cerberus --check knip --fix` regenerates `ignoreWorkspaces` from this declaration. Pyrefly requires strict typechecking of every Python kind, including demos and test harnesses. Story checks require public-interface stories only for eligible packages. Ordinary linting still covers all code.

Pyrefly requires `min-severity = "warn"` so warnings are displayed and fail the quality gate. Settings must be declared directly in `pyrefly.toml`; `extends` and command-line `--min-severity` overrides are rejected.

Other tools can consume the public API without scanning files or invoking the CLI:

```python
from pathlib import Path
from cerberus import load_source_scope

scope = load_source_scope(Path("/path/to/repository"))
scope.classify("infra/deploy.py").kind  # SourceKind.INFRASTRUCTURE
scope.classify("infra/deploy.py").requires_tests  # True
scope.classify_directory("infra").kind  # SourceKind.INFRASTRUCTURE
scope.is_test_file("apps/widget/tests/widget.test.tsx")  # True
scope.find_production_root("apps/widget/src/widget.tsx")  # "apps/widget"
```

`load_source_scope` reads the defaults and repository overlay. The returned `SourceScope` classifies repository-relative POSIX paths without filesystem access; the caller owns file discovery and any generated-file filtering.

### Python testing

```toml
[tool.pytest.ini_options]
addopts = "-p cerberus --cov --cov-report=term-missing"
testpaths = ["tests"]

[tool.coverage.run]
plugins = ["cerberus.coverage_plugin"]
patch = ["subprocess"]

[tool.coverage.report]
fail_under = 90
```

The pytest plugin skips demo-owned test files. The coverage configurer derives absolute source directories and omissions from the shared declaration and includes unexecuted namespace modules. Children inherit the prepared selection, including subprocesses that change directories. Package selectors such as `--cov=module` and handwritten coverage source/include/omit lists conflict with this ownership; the pytest bite reports them. It also checks that `testpaths` reaches every eligible conventional test file. This is configuration validation, not proof that every behavior has a test.

`zyplux_deps_latest` queries npm, PyPI, and GHCR at lint time; a failed lookup is reported as an error, never a silent pass. It has no `--fix` — run `just upgrade` to catch up.

`tool_pins_latest` requires the newest stable jscpd/fallow versions eligible under pnpm's one-day release quarantine. It runs only in the repo carrying `tool_pins.py`; consumers receive updated pins through Cerberus releases.

## Package and source checks

TypeScript seam checks use ESLint's resolved imports. The retired `cli_ts_test_seam`, `lib_ts_test_seam`, and `fixture_roles_ts` IDs report migration guidance when encountered in overlays. Their package policies are covered by the focused export, ownership, and reference checks.

Worker traversal covers first-party static imports and literal dynamic imports. Normal output summarizes static coverage limits; `--verbose` lists computed imports, third-party modules, and framework-provided entries that require production bundle validation.

Side-effect detection checks registration and initialization in workspace source modules against package-relative `sideEffects` paths. Packages publishing compiled files use patterns that also cover their compiled modules. The check cannot prove an arbitrary dependency graph pure.

Vitest coverage resolves exported literal objects and local constants, including `defineConfig` and its direct-return callbacks, without executing configuration code. Every metric meets the configured floor, and collection is enabled through `test.coverage.enabled: true` or the root test script's coverage flag.
