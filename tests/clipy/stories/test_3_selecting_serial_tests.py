from __future__ import annotations

import pytest


def test_3_1_1_runs_only_deferred_tests_selected_by_the_current_invocation(serial_tests: pytest.Pytester) -> None:
    assert serial_tests.runpytest_subprocess("--no-cov").ret == pytest.ExitCode.OK
    assert (serial_tests.path / "parallel-ran").exists()
    (serial_tests.path / "serial-ran").unlink()

    result = serial_tests.runpytest_subprocess("--no-cov", "-k", "parallel")

    assert result.ret == pytest.ExitCode.OK
    assert not (serial_tests.path / "serial-ran").exists()
    assert "tests coverage" not in result.stdout.str()


def test_3_1_2_runs_a_selected_serial_test_without_coverage_and_reports_success(
    serial_tests: pytest.Pytester,
) -> None:
    result = serial_tests.runpytest_subprocess("--no-cov", "-k", "test_serial")

    assert result.ret == pytest.ExitCode.OK
    assert (serial_tests.path / "serial-ran").exists()
    assert not (serial_tests.path / "parallel-ran").exists()
    assert "tests coverage" not in result.stdout.str()


@pytest.mark.parametrize("is_serial", [True, False])
def test_3_1_3_propagates_failures_from_serial_or_parallel_tests(
    serial_tests: pytest.Pytester, *, is_serial: bool
) -> None:
    marker = "@pytest.mark.no_xdist\n" if is_serial else ""
    serial_tests.makepyfile(test_failure=f"import pytest\n{marker}def test_failure():\n    assert False\n")

    result = serial_tests.runpytest_subprocess("--no-cov")

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    assert (serial_tests.path / "serial-ran").exists()
    assert (serial_tests.path / "parallel-ran").exists()


def test_3_1_4_collects_coverage_only_for_the_serial_test_package(serial_tests: pytest.Pytester) -> None:
    serial_tests.makeini("[pytest]\naddopts = -n 2 --cov=clipy --cov=totchef\nmarkers = no_xdist\n")

    result = serial_tests.runpytest_subprocess()

    assert result.ret == pytest.ExitCode.OK
    assert (serial_tests.path / "serial-ran").exists()
    assert (serial_tests.path / "parallel-ran").exists()
    assert "tests coverage" in result.stdout.str()
    assert "warnings summary" not in result.stdout.str()
