from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Finding, Status

type RunCheckWithFiles = Callable[[str, dict[str, str]], CheckResult]
type RunPyrefly = Callable[..., CheckResult]

CHECK_ID = "pyrefly-config"

_PYREFLY_STRICT = 'preset = "strict"\n\nproject-includes = ["apps/cerberus/src", "tests/cerberus"]\nsearch-path = ["apps/cerberus/src"]\n'

_PYREFLY_TESTS_RELAXED = _PYREFLY_STRICT + '\n[[sub-config]]\nmatches = "tests/cerberus/**"\n\n[sub-config.errors]\nimplicit-any = false\n'

_PY_PATHS = ["apps/cerberus/src/cerberus/cli.py", "tests/cerberus/test_cli.py"]


@pytest.fixture
def run_pyrefly(run_check_with_files: RunCheckWithFiles) -> RunPyrefly:
    def run(
        *,
        pyrefly: str | None = _PYREFLY_STRICT,
        pyproject: str | None = "[project]\n",
        paths: list[str] | None = None,
    ) -> CheckResult:
        files: dict[str, str] = dict.fromkeys(paths if paths is not None else _PY_PATHS, "")
        if pyproject is not None:
            files["pyproject.toml"] = pyproject
        if pyrefly is not None:
            files["pyrefly.toml"] = pyrefly
        return run_check_with_files(CHECK_ID, files)

    return run


def test_6_1_1_skips_repos_with_no_pyproject_file(run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]) -> None:
    result = run_pyrefly(pyproject=None)

    assert result.findings == [finding(status.SKIP, "no pyproject.toml (not a Python repo)")]


def test_6_1_2_skips_repos_with_a_pyproject_file_but_no_python_source(run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]) -> None:
    result = run_pyrefly(pyrefly=None, paths=["packages/ui/index.ts"])

    assert result.findings == [finding(status.SKIP, "no Python source")]


def test_6_2_1_fails_when_pyrefly_config_is_missing(run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]) -> None:
    result = run_pyrefly(pyrefly=None)

    assert result.findings == [finding(status.FAIL, 'no pyrefly.toml at repo root (org requires `preset = "strict"`)')]


def test_6_2_2_fails_when_pyrefly_config_lives_in_pyproject_instead(run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]) -> None:
    result = run_pyrefly(pyproject='[tool.pyrefly]\npreset = "strict"\n')

    assert result.findings == [finding(status.FAIL, "pyrefly config lives in pyproject.toml; move it to a standalone pyrefly.toml")]


def test_6_2_3_errors_when_pyrefly_config_cannot_be_parsed(run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]) -> None:
    result = run_pyrefly(pyrefly="preset = [unterminated\n")

    assert result.findings == [finding(status.ERROR, "could not parse pyrefly.toml")]


def test_6_3_1_fails_when_preset_is_not_strict(run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]) -> None:
    result = run_pyrefly(pyrefly='preset = "default"\n')

    assert result.findings == [finding(status.FAIL, "pyrefly.toml must set `preset = \"strict\"`; found 'default'")]


def test_6_4_1_fails_and_names_the_uncovered_production_root(run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]) -> None:
    pyrefly = _PYREFLY_STRICT.replace('"apps/cerberus/src", ', "")

    result = run_pyrefly(pyrefly=pyrefly)

    assert result.findings == [finding(status.FAIL, "pyrefly.toml project-includes does not cover: apps/cerberus/src")]


def test_6_4_2_fails_and_names_the_uncovered_test_root(run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]) -> None:
    pyrefly = _PYREFLY_STRICT.replace(', "tests/cerberus"]', "]")

    result = run_pyrefly(pyrefly=pyrefly)

    assert result.findings == [finding(status.FAIL, "pyrefly.toml project-includes does not cover: tests/cerberus")]


def test_6_5_1_fails_when_top_level_errors_weaken_strict_for_all_code(run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]) -> None:
    pyrefly = _PYREFLY_STRICT + "\n[errors]\nimplicit-any = false\n"

    result = run_pyrefly(pyrefly=pyrefly)

    assert result.findings == [finding(status.FAIL, "top-level errors table weakens strict on all code: implicit-any")]


def test_6_5_2_fails_when_an_error_kind_is_set_stray_at_the_top_level(run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]) -> None:
    pyrefly = _PYREFLY_STRICT.replace(
        'search-path = ["apps/cerberus/src"]\n',
        'search-path = ["apps/cerberus/src"]\nimplicit-any = false\n',
    )

    result = run_pyrefly(pyrefly=pyrefly)

    assert result.findings == [finding(status.FAIL, "pyrefly.toml sets error kinds at the top level, not under errors: implicit-any")]


@pytest.mark.parametrize("glob", ["apps/cerberus/src/**", "tests/cerberus/**"], ids=["production", "tests"])
def test_6_6_1_fails_when_a_sub_config_weakens_strict_for_production_or_test_code(
    run_pyrefly: RunPyrefly, glob: str, finding: type[Finding], status: type[Status]
) -> None:
    pyrefly = _PYREFLY_TESTS_RELAXED.replace('"tests/cerberus/**"', f'"{glob}"')

    result = run_pyrefly(pyrefly=pyrefly)

    assert result.findings == [finding(status.FAIL, f"sub-config `{glob}` weakens strict; no relaxations allowed: implicit-any")]


def test_6_6_2_fails_when_a_sub_config_entry_is_not_a_table(run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]) -> None:
    pyrefly = _PYREFLY_STRICT + '\nsub-config = ["oops"]\n'

    result = run_pyrefly(pyrefly=pyrefly)

    assert result.findings == [finding(status.FAIL, "pyrefly.toml sub-config entries must be tables; found 'oops'")]


def test_6_7_1_passes_when_preset_is_strict_coverage_is_complete_and_relaxations_are_absent(
    run_pyrefly: RunPyrefly, finding: type[Finding], status: type[Status]
) -> None:
    result = run_pyrefly()

    assert result.findings == [finding(status.PASS, "all code strict, no relaxations (pyrefly.toml)")]
