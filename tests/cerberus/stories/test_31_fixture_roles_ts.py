from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult
    from seam_fixtures import MakeFinding, RunCheckWithFiles

type RunFixtureRolesTests = Callable[[dict[str, str]], CheckResult]

CHECK_ID = "fixture_roles_ts"

_ROLES_ROOT_WS = '{"workspaces": ["apps/*", "packages/*", "tests/*"]}'
_ROLES_SUBJECT = '{"name": "@demo/app", "exports": {".": "./src/index.ts"}}'
_ROLES_SUITE = '{"name": "@demo/tests-app", "private": true, "imports": {"#fixtures": "./fixtures/index.ts"}}'
_ROLES_SUITE_FLAT_ALIAS = '{"name": "@demo/tests-app", "private": true, "imports": {"#fixtures": "./fixtures.ts"}}'
_ROLES_SUITE_NO_ALIAS = '{"name": "@demo/tests-app", "private": true}'
_ROLES_STORY = "import { test } from '#fixtures';\n"
_ROLES_ACT = "import { run } from '@demo/app';\n"
_ROLES_INDEX = "import { createRun } from './act';\n"
_ROLES_ARRANGE_PLAIN = "export const seedWidgets = 1;\n"

_ROLES_OK = "every suite's #fixtures alias targets fixtures/index.ts with fixtures/act.ts present"


def _suite_files(arrange: str = _ROLES_ARRANGE_PLAIN, suite_manifest: str = _ROLES_SUITE) -> dict[str, str]:
    return {
        "package.json": _ROLES_ROOT_WS,
        "apps/app/package.json": _ROLES_SUBJECT,
        "apps/app/src/index.ts": "",
        "tests/app/package.json": suite_manifest,
        "tests/app/stories/1-run.test.ts": _ROLES_STORY,
        "tests/app/fixtures/index.ts": _ROLES_INDEX,
        "tests/app/fixtures/act.ts": _ROLES_ACT,
        "tests/app/fixtures/arrange.ts": arrange,
    }


@pytest.fixture
def run_fixture_roles_tests(run_check_with_files: RunCheckWithFiles) -> RunFixtureRolesTests:
    return partial(run_check_with_files, CHECK_ID)


def test_31_1_1_skips_repos_with_no_typescript_packages(
    run_fixture_roles_tests: RunFixtureRolesTests, skip: MakeFinding
) -> None:
    result = run_fixture_roles_tests({})
    assert result.findings == [skip("no TypeScript packages")]


def test_31_1_2_skips_workspaces_with_no_torn_out_story_suite(
    run_fixture_roles_tests: RunFixtureRolesTests, skip: MakeFinding
) -> None:
    result = run_fixture_roles_tests({
        "package.json": _ROLES_ROOT_WS,
        "apps/app/package.json": _ROLES_SUBJECT,
        "apps/app/src/index.ts": "",
    })
    assert result.findings == [skip("no torn-out story suites")]


def test_31_2_1_passes_a_suite_with_the_role_layout(
    run_fixture_roles_tests: RunFixtureRolesTests, ok: MakeFinding
) -> None:
    result = run_fixture_roles_tests(_suite_files())
    assert result.findings == [ok(_ROLES_OK)]


def test_31_2_2_fails_a_fixtures_alias_pointing_at_a_single_fixtures_file(
    run_fixture_roles_tests: RunFixtureRolesTests, fail: MakeFinding
) -> None:
    result = run_fixture_roles_tests(_suite_files(suite_manifest=_ROLES_SUITE_FLAT_ALIAS))
    assert result.findings == [
        fail("tests/app/package.json: '#fixtures' must map to './fixtures/index.ts', got './fixtures.ts'")
    ]


def test_31_2_3_fails_a_suite_that_declares_no_fixtures_alias(
    run_fixture_roles_tests: RunFixtureRolesTests, fail: MakeFinding
) -> None:
    result = run_fixture_roles_tests(_suite_files(suite_manifest=_ROLES_SUITE_NO_ALIAS))
    assert result.findings == [fail("tests/app/package.json: no '#fixtures' alias targeting './fixtures/index.ts'")]


def test_31_2_4_fails_a_suite_missing_the_act_module(
    run_fixture_roles_tests: RunFixtureRolesTests, fail: MakeFinding
) -> None:
    files = _suite_files()
    del files["tests/app/fixtures/act.ts"]
    result = run_fixture_roles_tests(files)
    assert result.findings == [
        fail("tests/app/fixtures/act.ts: missing — act.ts is the fixture module that drives the subject package")
    ]
