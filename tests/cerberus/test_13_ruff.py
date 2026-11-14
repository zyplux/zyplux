from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Status
    from seam_fixtures import FakeProc, MakeFinding, RunCheckWithFiles

type RunRuff = Callable[..., CheckResult]

CHECK_ID = "ruff"

_RUFF_CANONICAL = (
    "line-length = 120\n"
    'target-version = "py314"\n'
    "preview = true\n\n"
    "[lint]\n"
    'select = ["ALL"]\n'
    'ignore = ["COM812", "ISC001", "D", "DOC", "CPY001", "S404", "S603", "S606", "S607"]\n\n'
    "[lint.per-file-ignores]\n"
    '"**/tests/**" = ["ANN001", "INP001", "S101"]\n'
)


@pytest.fixture
def run_ruff(run_check_with_files: RunCheckWithFiles) -> RunRuff:
    def _run(*, ruff: str | None = _RUFF_CANONICAL, pyproject: str | None = "[project]\n") -> CheckResult:
        files = {"pyproject.toml": pyproject, "ruff.toml": ruff, "app.py": ""}
        present = {path: content for path, content in files.items() if content is not None}
        return run_check_with_files(CHECK_ID, present)

    return _run


_OK_MESSAGE = 'ruff.toml is standalone, preview, select=["ALL"], relaxations within the sanctioned set'

_RULE_LISTING = json.dumps([
    {"name": "missing-trailing-comma", "code": "COM812"},
    {"name": "assert", "code": "S101"},
    {"name": "line-too-long", "code": "E501"},
])


def test_13_1_1_skips_repos_with_no_pyproject_file(run_ruff: RunRuff, skip: MakeFinding) -> None:
    result = run_ruff(pyproject=None)

    assert result.findings == [skip("no pyproject.toml (not a Python repo)")]


def test_13_2_1_fails_when_the_ruff_config_file_is_missing(run_ruff: RunRuff, fail: MakeFinding) -> None:
    result = run_ruff(ruff=None)

    assert result.findings == [fail("no ruff.toml at repo root (ruff config must be standalone)")]


def test_13_2_2_fails_when_the_ruff_config_lives_in_pyproject_instead(run_ruff: RunRuff, fail: MakeFinding) -> None:
    result = run_ruff(pyproject="[tool.ruff]\nline-length = 120\n")

    assert result.findings == [fail("ruff config lives in pyproject.toml; move it to a standalone ruff.toml")]


def test_13_2_3_errors_when_the_ruff_config_cannot_be_parsed(run_ruff: RunRuff, error: MakeFinding) -> None:
    result = run_ruff(ruff="preview = [unterminated\n")

    assert result.findings == [error("could not parse ruff.toml")]


@pytest.mark.parametrize(
    ("ruff", "found"),
    [
        (_RUFF_CANONICAL.replace("preview = true", "preview = false"), "False"),
        (_RUFF_CANONICAL.replace("preview = true\n", ""), "None"),
    ],
    ids=["off", "unset"],
)
def test_13_3_1_fails_unless_preview_is_explicitly_true(
    run_ruff: RunRuff, ruff: str, found: str, fail: MakeFinding
) -> None:
    result = run_ruff(ruff=ruff)

    assert result.findings == [fail(f"ruff.toml must set `preview = true` (found {found})")]


@pytest.mark.parametrize(
    ("ruff", "found"),
    [
        (_RUFF_CANONICAL.replace('select = ["ALL"]', 'select = ["E", "F"]'), "['E', 'F']"),
        ('preview = true\nselect = ["ALL"]\n', "None"),
    ],
    ids=["specific_rules", "top_level_select"],
)
def test_13_4_1_fails_unless_lint_select_is_exactly_all(
    run_ruff: RunRuff, ruff: str, found: str, fail: MakeFinding
) -> None:
    result = run_ruff(ruff=ruff)

    assert result.findings == [fail(f'ruff.toml must set `[lint] select = ["ALL"]` (found {found})')]


def test_13_5_1_passes_when_only_some_sanctioned_rules_are_ignored(run_ruff: RunRuff, ok: MakeFinding) -> None:
    result = run_ruff(ruff=_RUFF_CANONICAL.replace(', "S404", "S603", "S606", "S607"', ""))

    assert result.findings == [ok(_OK_MESSAGE)]


def test_13_5_2_fails_and_names_the_rule_when_an_ignore_falls_outside_the_sanctioned_set(
    run_ruff: RunRuff, fail: MakeFinding
) -> None:
    result = run_ruff(ruff=_RUFF_CANONICAL.replace('"S607"]', '"S607", "E501"]'))

    assert result.findings == [fail("ruff.toml ignores rules outside the sanctioned set: E501")]


def test_13_5_3_passes_when_a_sanctioned_ignore_is_spelled_as_ruffs_rule_name(
    run_ruff: RunRuff, fake_proc: FakeProc, ok: MakeFinding
) -> None:
    fake_proc.serve("ruff", stdout=_RULE_LISTING)

    result = run_ruff(ruff=_RUFF_CANONICAL.replace('"COM812"', '"missing-trailing-comma"'))

    assert result.findings == [ok(_OK_MESSAGE)]


def test_13_5_4_fails_and_echoes_the_spelling_when_an_ignore_spelled_as_a_rule_name_is_unsanctioned(
    run_ruff: RunRuff, fake_proc: FakeProc, fail: MakeFinding
) -> None:
    fake_proc.serve("ruff", stdout=_RULE_LISTING)

    result = run_ruff(ruff=_RUFF_CANONICAL.replace('"S607"]', '"S607", "line-too-long"]'))

    assert result.findings == [fail("ruff.toml ignores rules outside the sanctioned set: line-too-long")]


def test_13_5_5_errors_when_ruff_is_not_on_path_to_resolve_a_rule_name(
    run_ruff: RunRuff, fake_proc: FakeProc, error: MakeFinding
) -> None:
    fake_proc.serve_missing("ruff")

    result = run_ruff(ruff=_RUFF_CANONICAL.replace('"COM812"', '"missing-trailing-comma"'))

    assert result.findings == [
        error("could not resolve the rule names in ruff.toml to their codes: `ruff` not found on PATH")
    ]


def test_13_5_6_errors_when_ruff_cannot_list_its_rules(
    run_ruff: RunRuff, fake_proc: FakeProc, status: type[Status]
) -> None:
    fake_proc.serve("ruff", returncode=2, stderr="error: unexpected argument '--all'")

    result = run_ruff(ruff=_RUFF_CANONICAL.replace('"COM812"', '"missing-trailing-comma"'))

    assert result.findings[0].status == status.ERROR
    assert result.findings[0].message.startswith("could not resolve the rule names in ruff.toml to their codes:")


def test_13_6_1_passes_when_there_are_no_per_file_ignores(run_ruff: RunRuff, ok: MakeFinding) -> None:
    ruff = _RUFF_CANONICAL.split("\n[lint.per-file-ignores]", maxsplit=1)[0] + "\n"

    result = run_ruff(ruff=ruff)

    assert result.findings == [ok(_OK_MESSAGE)]


def test_13_6_2_passes_when_only_some_sanctioned_test_rules_are_relaxed(run_ruff: RunRuff, ok: MakeFinding) -> None:
    result = run_ruff(ruff=_RUFF_CANONICAL.replace('["ANN001", "INP001", "S101"]', '["S101"]'))

    assert result.findings == [ok(_OK_MESSAGE)]


def test_13_6_3_passes_regardless_of_which_glob_names_the_test_files(run_ruff: RunRuff, ok: MakeFinding) -> None:
    result = run_ruff(ruff=_RUFF_CANONICAL.replace('"**/tests/**"', '"tests/**"'))

    assert result.findings == [ok(_OK_MESSAGE)]


def test_13_6_4_fails_and_names_the_rule_when_a_test_relaxation_falls_outside_the_sanctioned_set(
    run_ruff: RunRuff, fail: MakeFinding
) -> None:
    result = run_ruff(ruff=_RUFF_CANONICAL.replace('"S101"]', '"S101", "ANN401"]'))

    assert result.findings == [
        fail("per-file-ignores `**/tests/**` relaxes rules outside the sanctioned test set: ANN401")
    ]


def test_13_6_5_passes_when_a_sanctioned_test_relaxation_is_spelled_as_ruffs_rule_name(
    run_ruff: RunRuff, fake_proc: FakeProc, ok: MakeFinding
) -> None:
    fake_proc.serve("ruff", stdout=_RULE_LISTING)

    result = run_ruff(ruff=_RUFF_CANONICAL.replace('"S101"]', '"assert"]'))

    assert result.findings == [ok(_OK_MESSAGE)]


def test_13_7_1_passes_when_preview_select_and_both_ignore_sets_are_fully_compliant(
    run_ruff: RunRuff, ok: MakeFinding
) -> None:
    result = run_ruff()

    assert result.findings == [ok(_OK_MESSAGE)]
