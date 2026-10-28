from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult
    from seam_fixtures import MakeFinding, RunCheckWithFiles

type RunPytestCoverage = Callable[[str | None], CheckResult]

CHECK_ID = "pytest"
PYPROJECT = "pyproject.toml"

_OK_MESSAGE = "pytest coverage gate enforces >= 90% ([tool.coverage.report] fail_under)"
_SELECTION = """
[tool.pytest.ini_options]
addopts = "-p cerberus --cov --cov-report=term-missing"
[tool.coverage.run]
plugins = ["cerberus.coverage_plugin"]
"""
_VALID_CONFIG = "[tool.coverage.report]\nfail_under = 90\n" + _SELECTION


@pytest.fixture
def run_pytest_coverage(run_check_with_files: RunCheckWithFiles) -> RunPytestCoverage:
    def _run(pyproject: str | None) -> CheckResult:
        files = {} if pyproject is None else {PYPROJECT: pyproject + _SELECTION, "app.py": ""}
        return run_check_with_files(CHECK_ID, files)

    return _run


def test_18_1_1_skips_repos_with_no_pyproject_file(run_pytest_coverage: RunPytestCoverage, skip: MakeFinding) -> None:
    result = run_pytest_coverage(None)

    assert result.findings == [skip("no pyproject.toml (not a Python repo)")]


def test_18_2_1_errors_when_pyproject_cannot_be_parsed(
    run_pytest_coverage: RunPytestCoverage, error: MakeFinding
) -> None:
    result = run_pytest_coverage("[project\nname = 'demo'\n")

    assert result.findings == [error("could not parse pyproject.toml")]


def test_18_2_2_fails_when_there_is_no_tool_coverage_report_fail_under(
    run_pytest_coverage: RunPytestCoverage, fail: MakeFinding
) -> None:
    result = run_pytest_coverage("[project]\nname = 'demo'\n")

    assert result.findings == [
        fail(
            "pyproject.toml has no [tool.coverage.report] fail_under; "
            "pytest coverage must enforce a floor of at least 90%",
        )
    ]


def test_18_2_3_fails_when_fail_under_is_not_a_number(
    run_pytest_coverage: RunPytestCoverage, fail: MakeFinding
) -> None:
    pyproject = "[project]\nname = 'demo'\n\n[tool.coverage.report]\nfail_under = 'ninety'\n"

    result = run_pytest_coverage(pyproject)

    assert result.findings == [
        fail("pyproject.toml [tool.coverage.report] fail_under must be a number; found 'ninety'")
    ]


def test_18_3_1_fails_when_fail_under_is_below_the_required_floor(
    run_pytest_coverage: RunPytestCoverage, fail: MakeFinding
) -> None:
    pyproject = "[project]\nname = 'demo'\n\n[tool.coverage.report]\nfail_under = 80\n"

    result = run_pytest_coverage(pyproject)

    assert result.findings == [fail("pyproject.toml [tool.coverage.report] fail_under is 80, below the required 90")]


@pytest.mark.parametrize("fail_under", [90, 95], ids=["at-floor", "above-floor"])
def test_18_3_2_passes_when_fail_under_meets_or_exceeds_the_required_floor(
    run_pytest_coverage: RunPytestCoverage, fail_under: int, ok: MakeFinding
) -> None:
    pyproject = f"[project]\nname = 'demo'\n\n[tool.coverage.report]\nfail_under = {fail_under}\n"

    result = run_pytest_coverage(pyproject)

    assert result.findings == [ok(_OK_MESSAGE)]


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (_VALID_CONFIG.replace('plugins = ["cerberus.coverage_plugin"]', "plugins = []"), "plugins must include"),
        (_VALID_CONFIG.replace("-p cerberus ", ""), "load the shared discovery policy"),
        (_VALID_CONFIG.replace("--cov ", "--cov=api "), "without package selectors"),
        (_VALID_CONFIG + 'omit = ["apps/api/**"]\n', "not coverage run.omit"),
    ],
)
def test_18_4_1_requires_source_and_discovery_selection_to_come_from_cerberus(
    run_check_with_files: RunCheckWithFiles, config: str, message: str
) -> None:
    result = run_check_with_files(CHECK_ID, {PYPROJECT: config, "apps/api/src/api.py": ""})
    assert any(message in finding.message for finding in result.problems)


def test_18_4_2_detects_test_directories_missing_from_pytest_discovery(run_check_with_files: RunCheckWithFiles) -> None:
    config = _VALID_CONFIG.replace("[tool.pytest.ini_options]", '[tool.pytest.ini_options]\ntestpaths = ["tests/unit"]')
    result = run_check_with_files(
        CHECK_ID,
        {
            PYPROJECT: config,
            "apps/api/src/api.py": "",
            "checks/test_api.py": "",
            "tests/demo/test_demo.py": "",
        },
        '[source]\ndemo_roots = ["tests/demo"]\n',
    )
    assert len(result.problems) == 1
    assert (
        result.problems[0].message
        == "pyproject.toml pytest testpaths does not collect eligible tests: checks/test_api.py"
    )


def test_18_4_3_does_not_require_tests_for_a_demo_only_repository(run_check_with_files: RunCheckWithFiles) -> None:
    result = run_check_with_files(CHECK_ID, {PYPROJECT: "[project]\n", "demo/app.py": ""})
    assert result.status.name == "SKIP"
