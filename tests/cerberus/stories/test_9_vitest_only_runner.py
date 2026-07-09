from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.context import Context
    from cerberus.model import CheckResult
    from seam_fixtures import MakeFinding, RunCheckWithFiles

type RunVitestRunner = Callable[..., CheckResult]

CHECK_ID = "vitest_only_runner"

_VITEST_PKG = '{"scripts": {"test": "vitest run"}}'
_BUN_TEST_PKG = '{"scripts": {"test": "bun test"}}'
_BUN_BAIL_TEST_PKG = '{"scripts": {"test": "bun --bail test"}}'
_BUN_FILTER_PKG = '{"scripts": {"test": "bun --filter \'*\' test"}}'
_BUN_RUN_PKG = '{"scripts": {"test": "bun run test"}}'
_VITEST_IMPORT = "import { describe, expect, it } from 'vitest';\n"
_BUN_TEST_IMPORT = "import { describe, expect, it } from 'bun:test';\n"


_OK_MESSAGE = "TypeScript tests run on vitest"


@pytest.fixture
def run_vitest_runner(
    monkeypatch: pytest.MonkeyPatch, ctx: Context, run_check_with_files: RunCheckWithFiles
) -> RunVitestRunner:
    def _run(files: dict[str, str], workflows: dict[str, str] | None = None) -> CheckResult:
        monkeypatch.setattr(ctx, "workflows", lambda _repo: workflows or {})
        return run_check_with_files(CHECK_ID, files)

    return _run


def test_9_1_1_skips_repos_with_no_package_json(run_vitest_runner: RunVitestRunner, skip: MakeFinding) -> None:
    result = run_vitest_runner({"README.md": "# demo\n"})
    assert result.findings == [skip("no package.json")]


@pytest.mark.parametrize("manifest", [_BUN_TEST_PKG, _BUN_BAIL_TEST_PKG], ids=["bare", "flagged"])
def test_9_2_1_fails_when_the_test_script_runs_bun_test_directly(
    run_vitest_runner: RunVitestRunner, manifest: str, fail: MakeFinding
) -> None:
    result = run_vitest_runner({"package.json": manifest, "src/a.test.ts": _VITEST_IMPORT})
    assert result.findings == [fail("package.json `test` script runs bun's test runner; use `vitest run`")]


def test_9_2_2_fails_when_a_nested_package_manifest_runs_bun_test(
    run_vitest_runner: RunVitestRunner, fail: MakeFinding
) -> None:
    result = run_vitest_runner({"package.json": _VITEST_PKG, "packages/a/package.json": _BUN_TEST_PKG})
    assert result.findings == [fail("packages/a/package.json `test` script runs bun's test runner; use `vitest run`")]


@pytest.mark.parametrize("manifest", [_BUN_FILTER_PKG, _BUN_RUN_PKG], ids=["bun_filter", "bun_run"])
def test_9_2_3_allows_bun_script_runner_invocations_of_the_test_script(
    run_vitest_runner: RunVitestRunner, manifest: str, ok: MakeFinding
) -> None:
    result = run_vitest_runner({"package.json": manifest})
    assert result.findings == [ok(_OK_MESSAGE)]


def test_9_2_4_treats_an_unparseable_manifest_as_having_no_test_script(
    run_vitest_runner: RunVitestRunner, ok: MakeFinding
) -> None:
    result = run_vitest_runner({"package.json": "not json"})
    assert result.findings == [ok(_OK_MESSAGE)]


def test_9_3_1_fails_when_a_test_file_imports_from_bun_test(
    run_vitest_runner: RunVitestRunner, fail: MakeFinding
) -> None:
    result = run_vitest_runner({"package.json": _VITEST_PKG, "src/a.test.ts": _BUN_TEST_IMPORT})
    assert result.findings == [fail("src/a.test.ts imports `bun:test`; import from `vitest` instead")]


def test_9_4_1_ignores_bun_test_scripts_and_imports_inside_vendored_node_modules(
    run_vitest_runner: RunVitestRunner, ok: MakeFinding
) -> None:
    result = run_vitest_runner({
        "package.json": _VITEST_PKG,
        "node_modules/dep/package.json": _BUN_TEST_PKG,
        "node_modules/dep/x.test.ts": _BUN_TEST_IMPORT,
    })
    assert result.findings == [ok(_OK_MESSAGE)]


def test_9_5_1_passes_when_the_test_script_and_test_files_both_use_vitest(
    run_vitest_runner: RunVitestRunner, ok: MakeFinding
) -> None:
    result = run_vitest_runner({"package.json": _VITEST_PKG, "src/a.test.ts": _VITEST_IMPORT})
    assert result.findings == [ok(_OK_MESSAGE)]


def test_9_6_1_fails_when_a_justfile_recipe_runs_bun_test(
    run_vitest_runner: RunVitestRunner, fail: MakeFinding
) -> None:
    result = run_vitest_runner({"package.json": _VITEST_PKG, "justfile": "test:\n    bun test\n"})
    assert result.findings == [fail("justfile runs bun's test runner; use `vitest run`")]


def test_9_6_2_fails_when_a_workflow_run_step_runs_bun_test(
    run_vitest_runner: RunVitestRunner, fail: MakeFinding
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - run: bun --bail test\n"
    result = run_vitest_runner({"package.json": _VITEST_PKG}, workflows={"ci.yml": wf})
    assert result.findings == [fail("ci.yml runs bun's test runner; use `vitest run`")]


def test_9_6_3_ignores_comment_lines_that_mention_bun_test(run_vitest_runner: RunVitestRunner, ok: MakeFinding) -> None:
    justfile = "# Run all workspace tests with bun test.\ntest:\n    bun run test\n"
    wf = "jobs:\n  ci:\n    steps:\n      - run: |\n          # not bun test\n          bun run test\n"
    result = run_vitest_runner({"package.json": _VITEST_PKG, "justfile": justfile}, workflows={"ci.yml": wf})
    assert result.findings == [ok(_OK_MESSAGE)]
