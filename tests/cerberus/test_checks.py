import shutil
from pathlib import Path

import pytest
from cerberus import config, context
from cerberus.checks import (
    catalog_discipline_check,
    cerberus_step_check,
    ci_sequence_check,
    ci_workflow_check,
    codeowners_check,
    justfile_check,
    pyrefly_config_check,
    rumdl_config_check,
    ts_project_references_check,
    vitest_runner_check,
    workflow_tooling_check,
)
from cerberus.model import Repo, Status

requires_just = pytest.mark.skipif(
    shutil.which("just") is None, reason="requires the `just` binary on PATH"
)

CONFORMING = """
alias i := install
alias k := knip
alias tc := typecheck
alias l := lint
alias t := test
alias c := check
alias u := upgrade
alias ui := upgrade-interactive

default:
    @just --list
install:
    bun install
knip:
    bun run knip
typecheck:
    bun run typecheck
lint:
    bun run lint
test:
    bun run test
check: install knip typecheck lint test
upgrade:
    bun run upgrade
upgrade-interactive:
    bun run upgrade -- -i
clean:
    rm -rf node_modules
"""

MISSING_REQUIRED_ALIAS = CONFORMING.replace("alias k := knip\n", "")
MISSING_RECOMMENDED = CONFORMING.replace("alias ui := upgrade-interactive\n", "").replace(
    "clean:\n    rm -rf node_modules\n", ""
)
WRONG_CHECK_ORDER = CONFORMING.replace(
    "check: install knip typecheck lint test", "check: install lint knip typecheck test"
)
BARE_TOOL_CALL = CONFORMING.replace("lint:\n    bun run lint\n", "lint:\n    rumdl check\n")
TRAILING_WHITESPACE = CONFORMING.replace(
    "check: install knip typecheck lint test\n",
    "check: install knip typecheck lint test   \n",
)


@pytest.fixture
def repo():
    return Repo("demo")


@pytest.fixture
def ctx():
    return context.local_context(config.load(), Path("."))


@requires_just
def test_conforming_justfile_passes(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: CONFORMING)
    assert justfile_check.run(repo, ctx).status is Status.PASS


def test_missing_justfile_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: None)
    assert justfile_check.run(repo, ctx).status is Status.FAIL


@requires_just
def test_missing_required_alias_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: MISSING_REQUIRED_ALIAS)
    assert justfile_check.run(repo, ctx).status is Status.FAIL


@requires_just
def test_missing_recommended_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: MISSING_RECOMMENDED)
    assert justfile_check.run(repo, ctx).status is Status.FAIL


@requires_just
def test_wrong_check_pipeline_order_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: WRONG_CHECK_ORDER)
    assert justfile_check.run(repo, ctx).status is Status.FAIL


@requires_just
def test_bare_managed_tool_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: BARE_TOOL_CALL)
    result = justfile_check.run(repo, ctx)
    assert result.status is Status.FAIL
    assert any("rumdl" in f.message for f in result.problems)


@requires_just
def test_trailing_whitespace_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: TRAILING_WHITESPACE)
    assert justfile_check.run(repo, ctx).status is Status.FAIL


def test_codeowners_missing_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: None)
    assert codeowners_check.run(repo, ctx).status is Status.FAIL


def test_codeowners_covers_github(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda r, p: "/.github/ @zyplux/admins\n")
    assert codeowners_check.run(repo, ctx).status is Status.PASS


def test_codeowners_wildcard_covers_github(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: "* @zyplux/admins\n")
    assert codeowners_check.run(repo, ctx).status is Status.PASS


def test_codeowners_lookalike_path_does_not_cover_github(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: "docs/.github-notes @zyplux/admins\n")
    assert codeowners_check.run(repo, ctx).status is Status.FAIL


def _ci_workflow(content):
    return lambda r, p: content if p.endswith((".yml", ".yaml")) else None


def test_ci_workflow_missing_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda r, p: None)
    assert ci_workflow_check.run(repo, ctx).status is Status.FAIL


def test_ci_workflow_invalid_yaml_errors(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", _ci_workflow("a: [unterminated"))
    assert ci_workflow_check.run(repo, ctx).status is Status.ERROR


def test_ci_workflow_non_mapping_errors(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", _ci_workflow("- just\n- a\n- list\n"))
    assert ci_workflow_check.run(repo, ctx).status is Status.ERROR


def test_ci_workflow_missing_ci_job_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(
        ctx, "file", _ci_workflow("on: [pull_request, push]\njobs:\n  build:\n    name: build\n")
    )
    assert ci_workflow_check.run(repo, ctx).status is Status.FAIL


def test_ci_workflow_missing_pull_request_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", _ci_workflow("on: push\njobs:\n  ci:\n    name: ci\n"))
    assert ci_workflow_check.run(repo, ctx).status is Status.FAIL


def test_ci_workflow_pull_request_only_passes(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", _ci_workflow("on: pull_request\njobs:\n  ci:\n    name: ci\n"))
    assert ci_workflow_check.run(repo, ctx).status is Status.PASS


def test_ci_workflow_on_as_pyyaml_bool_key(monkeypatch, repo, ctx):
    # Bare `on:` parses to the Python key True, not the string "on".
    monkeypatch.setattr(
        ctx, "file", _ci_workflow("on:\n  pull_request:\n  push:\njobs:\n  ci:\n    name: ci\n")
    )
    assert ci_workflow_check.run(repo, ctx).status is Status.PASS


def test_ci_workflow_job_id_named_ci_passes(monkeypatch, repo, ctx):
    monkeypatch.setattr(
        ctx, "file", _ci_workflow("on: [pull_request, push]\njobs:\n  ci:\n    runs-on: x\n")
    )
    assert ci_workflow_check.run(repo, ctx).status is Status.PASS


_CLEAN_WORKFLOW = (
    "jobs:\n"
    "  ci:\n"
    "    steps:\n"
    "      - uses: actions/checkout@v6\n"
    "      - uses: astral-sh/setup-uv@v8.2.0\n"
    "      - uses: oven-sh/setup-bun@v2\n"
    "      - run: uv sync --locked\n"
    "      - run: bun install --frozen-lockfile\n"
)


def test_workflow_tooling_passes_on_workspace_toolchain(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "workflows", lambda r: {"ci.yml": _CLEAN_WORKFLOW})
    assert workflow_tooling_check.run(repo, ctx).status is Status.PASS


def test_workflow_tooling_skips_without_workflows(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "workflows", lambda r: {})
    assert workflow_tooling_check.run(repo, ctx).status is Status.SKIP


def test_workflow_tooling_flags_setup_node(monkeypatch, repo, ctx):
    wf = "jobs:\n  ci:\n    steps:\n      - uses: actions/setup-node@v4\n"
    monkeypatch.setattr(ctx, "workflows", lambda r: {"ci.yml": wf})
    assert workflow_tooling_check.run(repo, ctx).status is Status.FAIL


def test_workflow_tooling_flags_install_action(monkeypatch, repo, ctx):
    wf = "jobs:\n  ci:\n    steps:\n      - uses: taiki-e/install-action@just\n"
    monkeypatch.setattr(ctx, "workflows", lambda r: {"ci.yml": wf})
    assert workflow_tooling_check.run(repo, ctx).status is Status.FAIL


def test_workflow_tooling_flags_apt_install(monkeypatch, repo, ctx):
    wf = "jobs:\n  ci:\n    steps:\n      - run: sudo apt-get install -y just\n"
    monkeypatch.setattr(ctx, "workflows", lambda r: {"ci.yml": wf})
    assert workflow_tooling_check.run(repo, ctx).status is Status.FAIL


def test_workflow_tooling_allows_npm_publish(monkeypatch, repo, ctx):
    wf = "jobs:\n  ci:\n    steps:\n      - run: npm publish ./*.tgz --access public\n"
    monkeypatch.setattr(ctx, "workflows", lambda r: {"ci.yml": wf})
    assert workflow_tooling_check.run(repo, ctx).status is Status.PASS


_RUMDL_CANONICAL = (
    "[global]\n"
    "disable = [\n"
    '    "MD013", # line-length\n'
    '    "MD022", # blanks-around-headings\n'
    '    "MD031", # blanks-around-fences\n'
    '    "MD032", # blanks-around-lists\n'
    '    "MD033", # no-inline-html\n'
    "]\n"
    "\n"
    "# no-duplicate-heading\n"
    "[MD024]\n"
    "siblings-only = true\n"
)
_RUMDL_OLD = '[global]\ndisable = ["MD033", "MD013"]\n\n[MD024]\nsiblings-only = true\n'


def test_rumdl_canonical_passes(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: _RUMDL_CANONICAL)
    assert rumdl_config_check.run(repo, ctx).status is Status.PASS


def test_rumdl_exclude_is_allowed(monkeypatch, repo, ctx):
    content = _RUMDL_CANONICAL.replace("]\n", ']\nexclude = ["reference_clones"]\n', 1)
    monkeypatch.setattr(ctx, "file", lambda *_: content)
    assert rumdl_config_check.run(repo, ctx).status is Status.PASS


def test_rumdl_old_config_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: _RUMDL_OLD)
    assert rumdl_config_check.run(repo, ctx).status is Status.FAIL


def test_rumdl_missing_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda *_: None)
    assert rumdl_config_check.run(repo, ctx).status is Status.FAIL


_PYREFLY_STRICT = (
    'preset = "strict"\n\n'
    'project-includes = ["apps/cerberus/src", "tests/cerberus"]\n'
    'search-path = ["apps/cerberus/src"]\n\n'
    "[[sub-config]]\n"
    'matches = "tests/cerberus/**"\n\n'
    "[sub-config.errors]\n"
    "implicit-any = false\n"
)

_PY_PATHS = ["apps/cerberus/src/cerberus/cli.py", "tests/cerberus/test_cli.py"]


def _pyrefly_ctx(monkeypatch, ctx, *, pyrefly=_PYREFLY_STRICT, pyproject="[project]\n", paths=None):
    files = {"pyproject.toml": pyproject, "pyrefly.toml": pyrefly}
    monkeypatch.setattr(ctx, "file", lambda r, p: files.get(p))
    monkeypatch.setattr(ctx, "paths", lambda r: _PY_PATHS if paths is None else paths)


def test_pyrefly_strict_passes(monkeypatch, repo, ctx):
    _pyrefly_ctx(monkeypatch, ctx)
    assert pyrefly_config_check.run(repo, ctx).status is Status.PASS


def test_pyrefly_skips_non_python(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", lambda r, p: None)
    assert pyrefly_config_check.run(repo, ctx).status is Status.SKIP


def test_pyrefly_skips_repo_without_python_source(monkeypatch, repo, ctx):
    _pyrefly_ctx(monkeypatch, ctx, pyrefly=None, paths=["packages/ui/index.ts"])
    assert pyrefly_config_check.run(repo, ctx).status is Status.SKIP


def test_pyrefly_missing_fails(monkeypatch, repo, ctx):
    _pyrefly_ctx(monkeypatch, ctx, pyrefly=None)
    assert pyrefly_config_check.run(repo, ctx).status is Status.FAIL


def test_pyrefly_wrong_preset_fails(monkeypatch, repo, ctx):
    _pyrefly_ctx(monkeypatch, ctx, pyrefly='preset = "default"\n')
    assert pyrefly_config_check.run(repo, ctx).status is Status.FAIL


def test_pyrefly_invalid_toml_errors(monkeypatch, repo, ctx):
    _pyrefly_ctx(monkeypatch, ctx, pyrefly="preset = [unterminated\n")
    assert pyrefly_config_check.run(repo, ctx).status is Status.ERROR


def test_pyrefly_config_in_pyproject_fails(monkeypatch, repo, ctx):
    _pyrefly_ctx(monkeypatch, ctx, pyproject='[tool.pyrefly]\npreset = "strict"\n')
    assert pyrefly_config_check.run(repo, ctx).status is Status.FAIL


def test_pyrefly_uncovered_production_fails(monkeypatch, repo, ctx):
    config = _PYREFLY_STRICT.replace('"apps/cerberus/src", ', "")
    _pyrefly_ctx(monkeypatch, ctx, pyrefly=config)
    result = pyrefly_config_check.run(repo, ctx)
    assert result.status is Status.FAIL
    assert any("apps/cerberus/src" in f.message for f in result.problems)


def test_pyrefly_weakened_production_fails(monkeypatch, repo, ctx):
    config = _PYREFLY_STRICT.replace('"tests/cerberus/**"', '"apps/cerberus/src/**"')
    _pyrefly_ctx(monkeypatch, ctx, pyrefly=config)
    result = pyrefly_config_check.run(repo, ctx)
    assert result.status is Status.FAIL
    assert any("weakens strict" in f.message for f in result.problems)


def test_pyrefly_tests_extra_override_fails(monkeypatch, repo, ctx):
    config = _PYREFLY_STRICT + "unused-ignore = false\n"
    _pyrefly_ctx(monkeypatch, ctx, pyrefly=config)
    result = pyrefly_config_check.run(repo, ctx)
    assert result.status is Status.FAIL
    assert any("tests" in f.message for f in result.problems)


def test_pyrefly_top_level_errors_weakening_fails(monkeypatch, repo, ctx):
    config = _PYREFLY_STRICT + "\n[errors]\nimplicit-any = false\n"
    _pyrefly_ctx(monkeypatch, ctx, pyrefly=config)
    result = pyrefly_config_check.run(repo, ctx)
    assert result.status is Status.FAIL
    assert any("top-level" in f.message for f in result.problems)


def test_pyrefly_stray_top_level_error_kind_fails(monkeypatch, repo, ctx):
    config = _PYREFLY_STRICT.replace(
        'search-path = ["apps/cerberus/src"]\n',
        'search-path = ["apps/cerberus/src"]\nimplicit-any = false\n',
    )
    _pyrefly_ctx(monkeypatch, ctx, pyrefly=config)
    result = pyrefly_config_check.run(repo, ctx)
    assert result.status is Status.FAIL
    assert any("implicit-any" in f.message for f in result.problems)


def test_pyrefly_fully_strict_tests_pass(monkeypatch, repo, ctx):
    config = (
        'preset = "strict"\n'
        'project-includes = ["apps/cerberus/src", "tests/cerberus"]\n'
        'search-path = ["apps/cerberus/src"]\n'
    )
    _pyrefly_ctx(monkeypatch, ctx, pyrefly=config)
    assert pyrefly_config_check.run(repo, ctx).status is Status.PASS


def test_rumdl_fix_normalizes_and_preserves_exclude(tmp_path):
    (tmp_path / ".rumdl.toml").write_text(
        '[global]\ndisable = ["MD033", "MD013"]\nexclude = ["reference_clones"]\n\n'
        "[MD024]\nsiblings-only = true\n"
    )
    fixer = context.local_context(config.load(), tmp_path, fix=True)
    target = fixer.repos()[0]
    rumdl_config_check.run(target, fixer)
    fixed = (tmp_path / ".rumdl.toml").read_text()
    assert 'exclude = ["reference_clones"]' in fixed
    assert "MD022" in fixed
    verifier = context.local_context(config.load(), tmp_path)
    assert rumdl_config_check.run(verifier.repos()[0], verifier).status is Status.PASS


def _wf(run_step):
    return {"ci.yml": f"jobs:\n  ci:\n    steps:\n      - run: {run_step}\n"}


def test_cerberus_step_present_passes(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "workflows", lambda r: _wf("uv run cerberus"))
    assert cerberus_step_check.run(repo, ctx).status is Status.PASS


def test_cerberus_step_uvx_form_passes(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "workflows", lambda r: _wf("uvx zyplux-cerberus"))
    assert cerberus_step_check.run(repo, ctx).status is Status.PASS


def test_cerberus_step_absent_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "workflows", lambda r: _wf("bun run test"))
    assert cerberus_step_check.run(repo, ctx).status is Status.FAIL


def test_cerberus_step_no_workflows_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "workflows", lambda r: {})
    assert cerberus_step_check.run(repo, ctx).status is Status.FAIL


def test_cerberus_step_broken_yaml_errors(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "workflows", lambda r: {"ci.yml": "jobs: [unterminated"})
    assert cerberus_step_check.run(repo, ctx).status is Status.ERROR


_PY_CI = (
    "jobs:\n  ci:\n    steps:\n"
    "      - run: uv sync --locked --all-groups\n"
    "      - run: uv run --no-sync vulture\n"
    "      - run: uv run --no-sync rumdl check\n"
    "      - run: uv run --no-sync ruff check\n"
    "      - run: uv run --no-sync ruff format --check\n"
    "      - run: uv run --no-sync pyrefly check\n"
    "      - run: uv run --no-sync pytest\n"
)
_TS_CI = (
    "jobs:\n  ci:\n    container: ghcr.io/zyplux/ci:1.3.14\n    steps:\n"
    "      - run: bun install --frozen-lockfile\n"
    "      - run: bun run knip\n"
    "      - run: bun run typecheck\n"
    "      - run: bun run lint\n"
    "      - run: bunx prettier --check .\n"
    "      - run: bun run test\n"
)


def _ci_files(*, python=False, ts=False, ci=""):
    def lookup(_repo, path):
        if path == "pyproject.toml":
            return "x" if python else None
        if path == "package.json":
            return "{}" if ts else None
        if path.endswith((".yml", ".yaml")):
            return ci or None
        return None

    return lookup


def test_ci_sequence_skips_without_manifest(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", _ci_files(ci=_PY_CI))
    assert ci_sequence_check.run(repo, ctx).status is Status.SKIP


def test_ci_sequence_python_canonical_passes(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", _ci_files(python=True, ci=_PY_CI))
    assert ci_sequence_check.run(repo, ctx).status is Status.PASS


def test_ci_sequence_python_missing_step_fails(monkeypatch, repo, ctx):
    ci = _PY_CI.replace("      - run: uv run --no-sync pytest\n", "")
    monkeypatch.setattr(ctx, "file", _ci_files(python=True, ci=ci))
    assert ci_sequence_check.run(repo, ctx).status is Status.FAIL


def test_ci_sequence_python_unlocked_sync_fails(monkeypatch, repo, ctx):
    ci = _PY_CI.replace("uv sync --locked --all-groups", "uv sync --all-groups")
    monkeypatch.setattr(ctx, "file", _ci_files(python=True, ci=ci))
    assert ci_sequence_check.run(repo, ctx).status is Status.FAIL


def test_ci_sequence_python_out_of_order_fails(monkeypatch, repo, ctx):
    ci = (
        "jobs:\n  ci:\n    steps:\n"
        "      - run: uv sync --locked --all-groups\n"
        "      - run: uv run --no-sync pyrefly check\n"
        "      - run: uv run --no-sync vulture\n"
        "      - run: uv run --no-sync rumdl check\n"
        "      - run: uv run --no-sync ruff check\n"
        "      - run: uv run --no-sync ruff format --check\n"
        "      - run: uv run --no-sync pytest\n"
    )
    monkeypatch.setattr(ctx, "file", _ci_files(python=True, ci=ci))
    assert ci_sequence_check.run(repo, ctx).status is Status.FAIL


def test_ci_sequence_ts_in_container_passes(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", _ci_files(ts=True, ci=_TS_CI))
    assert ci_sequence_check.run(repo, ctx).status is Status.PASS


def test_ci_sequence_ts_without_container_fails(monkeypatch, repo, ctx):
    ci = _TS_CI.replace("    container: ghcr.io/zyplux/ci:1.3.14\n", "")
    monkeypatch.setattr(ctx, "file", _ci_files(ts=True, ci=ci))
    assert ci_sequence_check.run(repo, ctx).status is Status.FAIL


def test_ci_sequence_ts_missing_step_fails(monkeypatch, repo, ctx):
    ci = _TS_CI.replace("      - run: bun run knip\n", "")
    monkeypatch.setattr(ctx, "file", _ci_files(ts=True, ci=ci))
    assert ci_sequence_check.run(repo, ctx).status is Status.FAIL


def test_ci_sequence_missing_ci_file_fails(monkeypatch, repo, ctx):
    monkeypatch.setattr(ctx, "file", _ci_files(python=True, ci=""))
    assert ci_sequence_check.run(repo, ctx).status is Status.FAIL


_VITEST_PKG = '{"scripts": {"test": "vitest run"}}'
_BUN_TEST_PKG = '{"scripts": {"test": "bun test"}}'
_BUN_FILTER_PKG = '{"scripts": {"test": "bun --filter \'*\' test"}}'
_BUN_RUN_PKG = '{"scripts": {"test": "bun run test"}}'
_VITEST_IMPORT = "import { describe, expect, it } from 'vitest';\n"
_BUN_TEST_IMPORT = "import { describe, expect, it } from 'bun:test';\n"


def _repo_files(mapping):
    def lookup(_repo, path):
        return mapping.get(path)

    return lookup


def _wire_files(monkeypatch, ctx, mapping):
    monkeypatch.setattr(ctx, "paths", lambda _repo: sorted(mapping))
    monkeypatch.setattr(ctx, "file", _repo_files(mapping))


def test_vitest_runner_skips_without_package_json(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"README.md": "# demo\n"})
    assert vitest_runner_check.run(repo, ctx).status is Status.SKIP


def test_vitest_runner_passes_on_vitest_repo(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _VITEST_PKG, "src/a.test.ts": _VITEST_IMPORT})
    assert vitest_runner_check.run(repo, ctx).status is Status.PASS


def test_vitest_runner_flags_bun_test_import(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _VITEST_PKG, "src/a.test.ts": _BUN_TEST_IMPORT})
    assert vitest_runner_check.run(repo, ctx).status is Status.FAIL


def test_vitest_runner_flags_bun_test_script(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _BUN_TEST_PKG, "src/a.test.ts": _VITEST_IMPORT})
    assert vitest_runner_check.run(repo, ctx).status is Status.FAIL


def test_vitest_runner_allows_bun_filter_script(monkeypatch, repo, ctx):
    _wire_files(
        monkeypatch, ctx, {"package.json": _BUN_FILTER_PKG, "src/a.test.ts": _VITEST_IMPORT}
    )
    assert vitest_runner_check.run(repo, ctx).status is Status.PASS


def test_vitest_runner_allows_bun_run_test_script(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _BUN_RUN_PKG})
    assert vitest_runner_check.run(repo, ctx).status is Status.PASS


def test_vitest_runner_ignores_node_modules(monkeypatch, repo, ctx):
    _wire_files(
        monkeypatch,
        ctx,
        {"package.json": _VITEST_PKG, "node_modules/dep/x.test.ts": _BUN_TEST_IMPORT},
    )
    assert vitest_runner_check.run(repo, ctx).status is Status.PASS


_TSB_PKG = '{"workspaces": ["packages/*"], "scripts": {"typecheck": "tsc -b"}}'
_TSBUILD_PKG = '{"workspaces": ["packages/*"], "scripts": {"typecheck": "tsc --build"}}'
_FANOUT_PKG = (
    '{"workspaces": ["packages/*"], "scripts": '
    '{"typecheck": "tsc -p . && bun --filter \'*\' typecheck"}}'
)
_TSC_P_PKG = (
    '{"workspaces": ["packages/*"], "scripts": {"typecheck": "tsc --noEmit -p tsconfig.json"}}'
)
_NO_TYPECHECK_PKG = '{"workspaces": ["packages/*"], "scripts": {"test": "vitest run"}}'
_NON_WORKSPACE_PKG = '{"scripts": {"typecheck": "tsc -b"}}'


def test_ts_project_references_skips_without_package_json(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"README.md": "# demo\n"})
    assert ts_project_references_check.run(repo, ctx).status is Status.SKIP


def test_ts_project_references_skips_non_workspace(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _NON_WORKSPACE_PKG, "tsconfig.json": "{}"})
    assert ts_project_references_check.run(repo, ctx).status is Status.SKIP


def test_ts_project_references_skips_without_tsconfig(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _TSB_PKG})
    assert ts_project_references_check.run(repo, ctx).status is Status.SKIP


def test_ts_project_references_passes_on_tsc_build(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _TSB_PKG, "tsconfig.json": "{}"})
    assert ts_project_references_check.run(repo, ctx).status is Status.PASS


def test_ts_project_references_passes_on_tsc_build_long_flag(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _TSBUILD_PKG, "tsconfig.json": "{}"})
    assert ts_project_references_check.run(repo, ctx).status is Status.PASS


def test_ts_project_references_flags_bun_filter_fanout(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _FANOUT_PKG, "tsconfig.json": "{}"})
    assert ts_project_references_check.run(repo, ctx).status is Status.FAIL


def test_ts_project_references_flags_single_project(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _TSC_P_PKG, "tsconfig.json": "{}"})
    assert ts_project_references_check.run(repo, ctx).status is Status.FAIL


def test_ts_project_references_flags_missing_typecheck(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _NO_TYPECHECK_PKG, "tsconfig.json": "{}"})
    assert ts_project_references_check.run(repo, ctx).status is Status.FAIL


_CATALOG_WS_ROOT = '{"workspaces": ["packages/*"], "devDependencies": {"eslint": "catalog:"}}'
_CATALOG_NON_WS = '{"dependencies": {"eslint": "^9.0.0"}}'
_CATALOG_PINNED_PKG = '{"dependencies": {"@zyplux/util": "workspace:*", "zod": "catalog:"}}'
_CATALOG_RAW_PKG = '{"dependencies": {"zod": "^3.0.0"}}'
_CATALOG_VENDORED_PKG = '{"dependencies": {"left-pad": "^1.0.0"}}'


def test_catalog_discipline_skips_non_workspace(monkeypatch, repo, ctx):
    _wire_files(monkeypatch, ctx, {"package.json": _CATALOG_NON_WS})
    assert catalog_discipline_check.run(repo, ctx).status is Status.SKIP


def test_catalog_discipline_passes_when_all_pinned(monkeypatch, repo, ctx):
    _wire_files(
        monkeypatch,
        ctx,
        {"package.json": _CATALOG_WS_ROOT, "packages/a/package.json": _CATALOG_PINNED_PKG},
    )
    assert catalog_discipline_check.run(repo, ctx).status is Status.PASS


def test_catalog_discipline_flags_raw_version(monkeypatch, repo, ctx):
    _wire_files(
        monkeypatch,
        ctx,
        {"package.json": _CATALOG_WS_ROOT, "packages/a/package.json": _CATALOG_RAW_PKG},
    )
    result = catalog_discipline_check.run(repo, ctx)
    assert result.status is Status.FAIL
    assert any("zod" in f.message for f in result.problems)


def test_catalog_discipline_ignores_node_modules(monkeypatch, repo, ctx):
    _wire_files(
        monkeypatch,
        ctx,
        {"package.json": _CATALOG_WS_ROOT, "node_modules/d/package.json": _CATALOG_VENDORED_PKG},
    )
    assert catalog_discipline_check.run(repo, ctx).status is Status.PASS
