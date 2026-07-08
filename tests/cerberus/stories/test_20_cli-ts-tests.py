from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Finding, Status

type RunCheckWithFiles = Callable[[str, dict[str, str]], CheckResult]
type RunCliTsTests = Callable[[dict[str, str]], CheckResult]

CHECK_ID = "cli-ts-tests"

_SEAM_ROOT_WS = '{"workspaces": ["apps/*", "packages/*"]}'
_SEAM_LIBRARY = '{"name": "@demo/lib", "exports": {".": "./src/index.ts", "./helpers": "./src/helpers.ts"}}'
_SEAM_CLI = (
    '{"name": "@demo/cli", "bin": {"cli": "./src/index.ts"},'
    ' "exports": {".": {"types": "./src/cli.ts", "default": "./src/cli.ts"}, "./package.json": "./package.json"}}'
)
_SEAM_CLI_NO_EXPORTS = '{"name": "@demo/cli", "bin": {"cli": "./src/index.ts"}}'
_SEAM_CLI_LEAKY = (
    '{"name": "@demo/cli", "bin": {"cli": "./src/index.ts"}, "exports": {".": "./src/cli.ts",'
    ' "./commands/deps-catalog": "./src/commands/deps-catalog.ts"}}'
)
_SEAM_CLI_NO_ROOT = (
    '{"name": "@demo/cli", "bin": {"cli": "./src/index.ts"}, "exports": {"./package.json": "./package.json"}}'
)
_SEAM_CLI_CONDITIONS = (
    '{"name": "@demo/cli", "bin": {"cli": "./src/index.ts"}, '
    '"exports": {"types": "./src/cli.ts", "default": "./src/cli.ts"}}'
)
_SEAM_TESTS_PKG = '{"name": "@demo/tests-cli", "imports": {"#fixtures": "./fixtures.ts"}}'
_SEAM_TESTS_PKG_SNEAKY = (
    '{"name": "@demo/tests-cli", "imports": {"#fixtures": "./fixtures.ts",'
    ' "#sneaky": "../../apps/cli/src/internal.ts"}}'
)
_SEAM_CLEAN_STORY = "import path from 'node:path';\n\nimport { describe, expect, test } from '#fixtures';\n"
_SEAM_APP_IMPORT_STORY = "import { runCli } from '@demo/cli';\n\nimport { test } from '#fixtures';\n"
_SEAM_RELATIVE_ESCAPE_STORY = (
    "import { internal } from '../../../apps/cli/src/internal.ts';\n\nimport { test } from '#fixtures';\n"
)

_SEAM_OK = "every cli app exports only the root seam; story tests reach workspace code only through fixture aliases"


@pytest.fixture
def run_cli_ts_tests(run_check_with_files: RunCheckWithFiles) -> RunCliTsTests:
    def _run(files: dict[str, str]) -> CheckResult:
        return run_check_with_files(CHECK_ID, files)

    return _run


def test_20_1_1_skips_repos_with_no_typescript_packages(
    run_cli_ts_tests: RunCliTsTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_ts_tests({})
    assert result.findings == [finding(status.SKIP, "no TypeScript packages")]


def test_20_1_2_skips_workspaces_with_no_cli_app(
    run_cli_ts_tests: RunCliTsTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_ts_tests({
        "package.json": _SEAM_ROOT_WS,
        "packages/lib/package.json": _SEAM_LIBRARY,
    })
    assert result.findings == [finding(status.SKIP, "no cli apps")]


def test_20_2_1_passes_a_cli_app_that_exports_only_the_root_seam(
    run_cli_ts_tests: RunCliTsTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_ts_tests({
        "package.json": _SEAM_ROOT_WS,
        "apps/cli/package.json": _SEAM_CLI,
    })
    assert result.findings == [finding(status.PASS, _SEAM_OK)]


def test_20_2_2_fails_a_cli_app_that_declares_no_exports(
    run_cli_ts_tests: RunCliTsTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_ts_tests({
        "package.json": _SEAM_ROOT_WS,
        "apps/cli/package.json": _SEAM_CLI_NO_EXPORTS,
    })
    assert result.findings == [
        finding(
            status.FAIL,
            "apps/cli/package.json: cli app must declare exports; without one every internal module is importable",
        )
    ]


def test_20_2_3_fails_and_names_each_export_beyond_the_root_seam(
    run_cli_ts_tests: RunCliTsTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_ts_tests({
        "package.json": _SEAM_ROOT_WS,
        "apps/cli/package.json": _SEAM_CLI_LEAKY,
    })
    assert result.findings == [
        finding(
            status.FAIL,
            "apps/cli/package.json: cli app exports expose more than the root seam — './commands/deps-catalog'",
        )
    ]


def test_20_2_4_fails_a_cli_app_whose_exports_omit_the_root_entry(
    run_cli_ts_tests: RunCliTsTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_ts_tests({
        "package.json": _SEAM_ROOT_WS,
        "apps/cli/package.json": _SEAM_CLI_NO_ROOT,
    })
    assert result.findings == [
        finding(status.FAIL, "apps/cli/package.json: cli app exports must include the '.' root seam")
    ]


def test_20_2_5_accepts_a_conditions_object_as_the_root_seam(
    run_cli_ts_tests: RunCliTsTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_ts_tests({
        "package.json": _SEAM_ROOT_WS,
        "apps/cli/package.json": _SEAM_CLI_CONDITIONS,
    })
    assert result.findings == [finding(status.PASS, _SEAM_OK)]


def test_20_3_1_passes_story_tests_importing_only_fixture_aliases_and_node_builtins(
    run_cli_ts_tests: RunCliTsTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_ts_tests({
        "package.json": _SEAM_ROOT_WS,
        "apps/cli/package.json": _SEAM_CLI,
        "tests/cli/package.json": _SEAM_TESTS_PKG,
        "tests/cli/stories/1-first.test.ts": _SEAM_CLEAN_STORY,
    })
    assert result.findings == [finding(status.PASS, _SEAM_OK)]


def test_20_3_2_fails_a_story_test_importing_the_app_package_directly(
    run_cli_ts_tests: RunCliTsTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_ts_tests({
        "package.json": _SEAM_ROOT_WS,
        "apps/cli/package.json": _SEAM_CLI,
        "tests/cli/package.json": _SEAM_TESTS_PKG,
        "tests/cli/stories/1-first.test.ts": _SEAM_APP_IMPORT_STORY,
    })
    assert result.findings == [
        finding(
            status.FAIL,
            "tests/cli/stories/1-first.test.ts: story test imports outside the fixtures seam — '@demo/cli'",
        )
    ]


def test_20_3_3_fails_a_story_test_reaching_into_app_internals_via_a_relative_path(
    run_cli_ts_tests: RunCliTsTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_ts_tests({
        "package.json": _SEAM_ROOT_WS,
        "apps/cli/package.json": _SEAM_CLI,
        "tests/cli/package.json": _SEAM_TESTS_PKG,
        "tests/cli/stories/1-first.test.ts": _SEAM_RELATIVE_ESCAPE_STORY,
    })
    assert result.findings == [
        finding(
            status.FAIL,
            "tests/cli/stories/1-first.test.ts: story test imports outside the fixtures seam — "
            "'../../../apps/cli/src/internal.ts'",
        )
    ]


def test_20_4_1_fails_an_imports_alias_that_escapes_the_test_package(
    run_cli_ts_tests: RunCliTsTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_ts_tests({
        "package.json": _SEAM_ROOT_WS,
        "apps/cli/package.json": _SEAM_CLI,
        "tests/cli/package.json": _SEAM_TESTS_PKG_SNEAKY,
        "tests/cli/stories/1-first.test.ts": _SEAM_CLEAN_STORY,
    })
    assert result.findings == [
        finding(
            status.FAIL,
            "tests/cli/package.json: imports alias escapes the test package — "
            "'#sneaky' -> '../../apps/cli/src/internal.ts'",
        )
    ]
