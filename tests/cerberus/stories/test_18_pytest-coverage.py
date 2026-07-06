from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Finding, Status

type RunCheckWithFiles = Callable[[str, dict[str, str]], CheckResult]
type RunPytestCoverage = Callable[[str | None], CheckResult]

CHECK_ID = "pytest-coverage"
PYPROJECT = "pyproject.toml"

_OK_MESSAGE = "pytest coverage gate enforces >= 90% ([tool.coverage.report] fail_under)"


@pytest.fixture
def run_pytest_coverage(run_check_with_files: RunCheckWithFiles) -> RunPytestCoverage:
    def _run(pyproject: str | None) -> CheckResult:
        files = {} if pyproject is None else {PYPROJECT: pyproject}
        return run_check_with_files(CHECK_ID, files)

    return _run


def test_18_1_1_skips_repos_with_no_pyproject_file(
    run_pytest_coverage: RunPytestCoverage, finding: type[Finding], status: type[Status]
) -> None:
    result = run_pytest_coverage(None)

    assert result.findings == [finding(status.SKIP, "no pyproject.toml (not a Python repo)")]


def test_18_2_1_errors_when_pyproject_cannot_be_parsed(
    run_pytest_coverage: RunPytestCoverage, finding: type[Finding], status: type[Status]
) -> None:
    result = run_pytest_coverage("[project\nname = 'demo'\n")

    assert result.findings == [finding(status.ERROR, "could not parse pyproject.toml")]


def test_18_2_2_fails_when_there_is_no_tool_coverage_report_fail_under(
    run_pytest_coverage: RunPytestCoverage, finding: type[Finding], status: type[Status]
) -> None:
    result = run_pytest_coverage("[project]\nname = 'demo'\n")

    assert result.findings == [
        finding(
            status.FAIL,
            "pyproject.toml has no [tool.coverage.report] fail_under; "
            "pytest coverage must enforce a floor of at least 90%",
        )
    ]


def test_18_2_3_fails_when_fail_under_is_not_a_number(
    run_pytest_coverage: RunPytestCoverage, finding: type[Finding], status: type[Status]
) -> None:
    pyproject = "[project]\nname = 'demo'\n\n[tool.coverage.report]\nfail_under = 'ninety'\n"

    result = run_pytest_coverage(pyproject)

    assert result.findings == [
        finding(status.FAIL, "pyproject.toml [tool.coverage.report] fail_under must be a number; found 'ninety'")
    ]


def test_18_3_1_fails_when_fail_under_is_below_the_required_floor(
    run_pytest_coverage: RunPytestCoverage, finding: type[Finding], status: type[Status]
) -> None:
    pyproject = "[project]\nname = 'demo'\n\n[tool.coverage.report]\nfail_under = 80\n"

    result = run_pytest_coverage(pyproject)

    assert result.findings == [
        finding(status.FAIL, "pyproject.toml [tool.coverage.report] fail_under is 80, below the required 90")
    ]


@pytest.mark.parametrize("fail_under", [90, 95], ids=["at-floor", "above-floor"])
def test_18_3_2_passes_when_fail_under_meets_or_exceeds_the_required_floor(
    run_pytest_coverage: RunPytestCoverage, fail_under: int, finding: type[Finding], status: type[Status]
) -> None:
    pyproject = f"[project]\nname = 'demo'\n\n[tool.coverage.report]\nfail_under = {fail_under}\n"

    result = run_pytest_coverage(pyproject)

    assert result.findings == [finding(status.PASS, _OK_MESSAGE)]
