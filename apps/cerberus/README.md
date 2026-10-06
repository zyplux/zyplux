# cerberus

Verifies repository invariants — CI workflow structure, justfile and dependency conventions, CODEOWNERS, and release-version bumps — as a per-repo linter against a checkout.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) and Python 3.14

The `justfile` bite shells out to `just`, which ships with the package (via [`rust-just`](https://pypi.org/project/rust-just/)) — no separate install. The `jscpd` and `fallow` bites run their tools via `pnpx` at exact versions pinned in [`tool_pins.py`](src/cerberus/tool_pins.py), so every cerberus release measures with the same tools everywhere; `pnpm` must be on PATH.

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
| `justfile`                     | content     | Recipe names, aliases, ordered `check` dependencies and body calls, local cerberus run, wrapped tool calls, no trailing whitespace |
| `ci_workflow_gate`             | content     | `ci.yml` exists, exposes a `ci` check, runs on PRs (push to `main` recommended)      |
| `ci_check_sequence`            | content     | `ci.yml` runs the canonical check sequence per stack          |
| `ci_cerberus_step`             | content     | A CI workflow runs cerberus to self-verify org invariants                           |
| `workflow_toolchain_only`      | content     | Workflows set up only the workspace toolchain (uv, pnpm), not extra tools            |
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
| `release_surface_version_bump` | git-history | A published target's version is bumped by exactly one step whenever its release surface changes |
| `codeowners_coverage`          | content     | `CODEOWNERS` present and covers `/.github/`                                          |
| `pytest`                       | content     | `pyproject.toml` `[tool.coverage.report] fail_under` meets the floor (90%)           |
| `jscpd`                        | content     | Copy-paste duplication per language stays under the configured jscpd threshold      |
| `fallow`                       | content     | fallow finds no unused code, circular imports, or functions above its complexity thresholds |
| `zyplux_deps_latest`           | content     | Every `@zyplux/*` npm package, `zyplux-*` PyPI distribution, and `ghcr.io/zyplux` image is used at its latest release |
| `tool_pins_latest`             | content     | The npm tool versions pinned in cerberus source are the latest npm releases (skips repos not carrying the pin source) |

## Justfile recipes

[`baseline.just`](src/cerberus/baseline.just) is the starting template. Cerberus checks names, aliases, ordered gate steps and their actual tool calls, managed-tool runners, cleanup, and whitespace. Required calls run as standalone foreground commands that preserve failures; local shell helpers enable `set -e`. The test recipe may guard runners by their workspace manifests and accept pytest's empty-suite exit code. Application recipes may add parameters, modules, and commands; `--fix` removes trailing whitespace.

## Fallow inputs

`[fallow].entry_points` registers exact repository files loaded by framework or runtime conventions that Fallow cannot infer. Every declared file must exist. `[fallow].coverage_report` defaults to `coverage/coverage-final.json`; when present, the health analysis uses it for measured CRAP scores. Run tests before Cerberus to refresh the report. Dead-code analysis and complexity thresholds use the shared policy.

## Config

Every default lives in [`cerberus.toml`](src/cerberus/cerberus.toml): shared source ownership under `[source]`, and check settings under their bite's table (`[justfile]`, `[pytest]`, `[jscpd]`, …). The bundled file is the single home of the defaults; missing required keys are errors. A repo adjusts them with a root `cerberus.toml`, overlaid key by key. An explicit `--config PATH` stands in for that repository file. Lists replace the corresponding default list.

Every bite table also takes a common `off` key, handled by the runner: `off = true` removes the bite from the run entirely — no output line — and an overlay's `off = false` re-enables a bite the bundled defaults ship off. `tool_pins_latest` ships off for exactly that reason: only the repo carrying the pin source can act on it, and that repo's overlay switches it on.

### Shared source ownership

```toml
[source]
production_roots = ["apps/*", "packages/*", "infra"]
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

Production roots are repository-relative directory globs; their descendants belong to production, including source assets, build configuration, and deployment infrastructure. Test-file globs take precedence even inside a production root. `*` matches one path segment and `**` spans directories. Files outside both selections are other maintained files, such as development tooling. These conventions apply independently of which bites are enabled.

Knip intersects this ownership with registered JavaScript workspaces; a standalone root package remains production. Pyrefly requires coverage of production and test Python source, including flat `infra/deploy.py` and deeply nested roots. It reports a production root's `src` subtree when the file lives there. Both checks consume the same classification; `[knip].prod_workspaces` and `[pyrefly].prod_workspaces` must be replaced by `[source].production_roots`, with conflicting lists reconciled by the repository owner.

Other tools can consume the public API without scanning files or invoking the CLI:

```python
from pathlib import Path
from cerberus import load_source_scope

scope = load_source_scope(Path("/path/to/repository"))
scope.is_production_file("infra/deploy.py")  # True with bundled defaults
scope.is_test_file("apps/widget/tests/widget.test.tsx")  # True
scope.find_production_root("apps/widget/src/widget.tsx")  # "apps/widget"
```

`load_source_scope` reads the defaults and repository overlay. The returned `SourceScope` classifies repository-relative POSIX paths without filesystem access; the caller owns file discovery and any generated-file filtering.

`zyplux_deps_latest` queries npm, PyPI, and GHCR at lint time; a failed lookup is reported as an error, never a silent pass. It has no `--fix` — run `just upgrade` to catch up.

`tool_pins_latest` guards the jscpd/fallow pins the same way, but runs only in the repo that carries `tool_pins.py` — the one place a pin can be bumped. Consumer repos never see it (bundled `off = true`) and pick new pins up with the next cerberus release, which `zyplux_deps_latest` already forces them onto.

## Package and source checks

TypeScript seam checks use ESLint's resolved imports. The retired `cli_ts_test_seam`, `lib_ts_test_seam`, and `fixture_roles_ts` IDs report migration guidance when encountered in overlays. Their package policies are covered by the focused export, ownership, and reference checks.

Worker traversal covers first-party static imports and literal dynamic imports. Normal output summarizes static coverage limits; `--verbose` lists computed imports, third-party modules, and framework-provided entries that require production bundle validation.

Side-effect detection checks registration and initialization in workspace source modules against package-relative `sideEffects` paths. Packages publishing compiled files use patterns that also cover their compiled modules. The check cannot prove an arbitrary dependency graph pure.

Vitest coverage resolves exported literal objects and local constants, including `defineConfig` and its direct-return callbacks, without executing configuration code. Every metric meets the configured floor, and collection is enabled through `test.coverage.enabled: true` or the root test script's coverage flag.
