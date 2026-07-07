from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Finding, Status

type RunCheckWithFiles = Callable[[str, dict[str, str]], CheckResult]
type RunRuff = Callable[..., CheckResult]

CHECK_ID = "ruff-config"

_RUFF_CANONICAL = (
    "line-length = 160\n"
    'target-version = "py314"\n'
    "preview = true\n\n"
    "[lint]\n"
    'select = ["ALL"]\n'
    'ignore = ["COM812", "ISC001", "D", "DOC", "CPY001", "S404", "S603", "S607"]\n\n'
    "[lint.per-file-ignores]\n"
    '"**/tests/**" = ["ANN001", "INP001", "S101"]\n'
)


@pytest.fixture
def run_ruff(run_check_with_files: RunCheckWithFiles) -> RunRuff:
    def _run(*, ruff: str | None = _RUFF_CANONICAL, pyproject: str | None = "[project]\n") -> CheckResult:
        files = {"pyproject.toml": pyproject, "ruff.toml": ruff}
        present = {path: content for path, content in files.items() if content is not None}
        return run_check_with_files(CHECK_ID, present)

    return _run


def _pass_finding(finding: type[Finding], status: type[Status]) -> Finding:
    return finding(status.PASS, 'ruff.toml is standalone, preview, select=["ALL"], relaxations within the sanctioned set')


def test_13_1_1_skips_repos_with_no_pyproject_file(run_ruff: RunRuff, finding: type[Finding], status: type[Status]) -> None:
    result = run_ruff(pyproject=None)

    assert result.findings == [finding(status.SKIP, "no pyproject.toml (not a Python repo)")]


def test_13_2_1_fails_when_the_ruff_config_file_is_missing(run_ruff: RunRuff, finding: type[Finding], status: type[Status]) -> None:
    result = run_ruff(ruff=None)

    assert result.findings == [finding(status.FAIL, "no ruff.toml at repo root (ruff config must be standalone)")]


def test_13_2_2_fails_when_the_ruff_config_lives_in_pyproject_instead(run_ruff: RunRuff, finding: type[Finding], status: type[Status]) -> None:
    result = run_ruff(pyproject="[tool.ruff]\nline-length = 160\n")

    assert result.findings == [finding(status.FAIL, "ruff config lives in pyproject.toml; move it to a standalone ruff.toml")]


def test_13_2_3_errors_when_the_ruff_config_cannot_be_parsed(run_ruff: RunRuff, finding: type[Finding], status: type[Status]) -> None:
    result = run_ruff(ruff="preview = [unterminated\n")

    assert result.findings == [finding(status.ERROR, "could not parse ruff.toml")]


@pytest.mark.parametrize(
    ("ruff", "found"),
    [
        (_RUFF_CANONICAL.replace("preview = true", "preview = false"), "False"),
        (_RUFF_CANONICAL.replace("preview = true\n", ""), "None"),
    ],
    ids=["off", "unset"],
)
def test_13_3_1_fails_unless_preview_is_explicitly_true(run_ruff: RunRuff, ruff: str, found: str, finding: type[Finding], status: type[Status]) -> None:
    result = run_ruff(ruff=ruff)

    assert result.findings == [finding(status.FAIL, f"ruff.toml must set `preview = true` (found {found})")]


@pytest.mark.parametrize(
    ("ruff", "found"),
    [
        (_RUFF_CANONICAL.replace('select = ["ALL"]', 'select = ["E", "F"]'), "['E', 'F']"),
        ('preview = true\nselect = ["ALL"]\n', "None"),
    ],
    ids=["specific_rules", "top_level_select"],
)
def test_13_4_1_fails_unless_lint_select_is_exactly_all(run_ruff: RunRuff, ruff: str, found: str, finding: type[Finding], status: type[Status]) -> None:
    result = run_ruff(ruff=ruff)

    assert result.findings == [finding(status.FAIL, f'ruff.toml must set `[lint] select = ["ALL"]` (found {found})')]


def test_13_5_1_passes_when_only_some_sanctioned_rules_are_ignored(run_ruff: RunRuff, finding: type[Finding], status: type[Status]) -> None:
    result = run_ruff(ruff=_RUFF_CANONICAL.replace(', "S404", "S603", "S607"', ""))

    assert result.findings == [_pass_finding(finding, status)]


def test_13_5_2_fails_and_names_the_rule_when_an_ignore_falls_outside_the_sanctioned_set(
    run_ruff: RunRuff, finding: type[Finding], status: type[Status]
) -> None:
    result = run_ruff(ruff=_RUFF_CANONICAL.replace('"S607"]', '"S607", "E501"]'))

    assert result.findings == [finding(status.FAIL, "ruff.toml ignores rules outside the sanctioned set: E501")]


def test_13_6_1_passes_when_there_are_no_per_file_ignores(run_ruff: RunRuff, finding: type[Finding], status: type[Status]) -> None:
    ruff = _RUFF_CANONICAL.split("\n[lint.per-file-ignores]", maxsplit=1)[0] + "\n"

    result = run_ruff(ruff=ruff)

    assert result.findings == [_pass_finding(finding, status)]


def test_13_6_2_passes_when_only_some_sanctioned_test_rules_are_relaxed(run_ruff: RunRuff, finding: type[Finding], status: type[Status]) -> None:
    result = run_ruff(ruff=_RUFF_CANONICAL.replace('["ANN001", "INP001", "S101"]', '["S101"]'))

    assert result.findings == [_pass_finding(finding, status)]


def test_13_6_3_passes_regardless_of_which_glob_names_the_test_files(run_ruff: RunRuff, finding: type[Finding], status: type[Status]) -> None:
    result = run_ruff(ruff=_RUFF_CANONICAL.replace('"**/tests/**"', '"tests/**"'))

    assert result.findings == [_pass_finding(finding, status)]


def test_13_6_4_fails_and_names_the_rule_when_a_test_relaxation_falls_outside_the_sanctioned_set(
    run_ruff: RunRuff, finding: type[Finding], status: type[Status]
) -> None:
    result = run_ruff(ruff=_RUFF_CANONICAL.replace('"S101"]', '"S101", "ANN401"]'))

    assert result.findings == [finding(status.FAIL, "per-file-ignores `**/tests/**` relaxes rules outside the sanctioned test set: ANN401")]


def test_13_7_1_passes_when_preview_select_and_both_ignore_sets_are_fully_compliant(run_ruff: RunRuff, finding: type[Finding], status: type[Status]) -> None:
    result = run_ruff()

    assert result.findings == [_pass_finding(finding, status)]
