from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult
    from seam_fixtures import MakeFinding, RunCheckWithFiles

type RunLineLength = Callable[[dict[str, str]], CheckResult]

CHECK_ID = "line-length"

RUFF_120 = "line-length = 120\n"
PRETTIER_120 = "const config = {\n  printWidth: 120,\n};\n"


@pytest.fixture
def run_line_length(run_check_with_files: RunCheckWithFiles) -> RunLineLength:
    return partial(run_check_with_files, CHECK_ID)


def test_12_1_1_skips_repos_with_neither_a_ruff_nor_a_prettier_config(
    run_line_length: RunLineLength, skip: MakeFinding
) -> None:
    result = run_line_length({})
    assert result.findings == [skip("no ruff or prettier config")]


def test_12_1_2_passes_when_only_a_ruff_config_is_present_and_correct(
    run_line_length: RunLineLength, ok: MakeFinding
) -> None:
    result = run_line_length({"ruff.toml": RUFF_120})
    assert result.findings == [ok("ruff and prettier both wrap at 120")]


@pytest.mark.parametrize(
    ("path", "content"),
    [("prettier.config.ts", PRETTIER_120), (".prettierrc", '{"printWidth": 120}')],
    ids=["config_ts", "prettierrc"],
)
def test_12_1_3_passes_when_only_a_prettier_config_is_present_and_correct(
    run_line_length: RunLineLength, path: str, content: str, ok: MakeFinding
) -> None:
    result = run_line_length({path: content})
    assert result.findings == [ok("ruff and prettier both wrap at 120")]


def test_12_2_1_fails_when_ruff_sets_a_different_line_length(run_line_length: RunLineLength, fail: MakeFinding) -> None:
    result = run_line_length({"ruff.toml": "line-length = 100\n", "prettier.config.ts": PRETTIER_120})
    assert result.findings == [fail("ruff.toml sets line-length = 100, expected 120")]


@pytest.mark.parametrize("ruff", ["[lint]\n", "line-length = [unterminated\n"], ids=["unset", "invalid_toml"])
def test_12_2_2_fails_when_ruff_does_not_set_a_line_length(
    run_line_length: RunLineLength, ruff: str, fail: MakeFinding
) -> None:
    result = run_line_length({"ruff.toml": ruff, "prettier.config.ts": PRETTIER_120})
    assert result.findings == [fail("ruff.toml does not set line-length = 120")]


def test_12_3_1_fails_when_prettier_sets_a_different_line_length(
    run_line_length: RunLineLength, fail: MakeFinding
) -> None:
    result = run_line_length({"ruff.toml": RUFF_120, "prettier.config.ts": "export default { printWidth: 80 };\n"})
    assert result.findings == [fail("prettier.config.ts sets printWidth = 80, expected 120")]


def test_12_3_2_fails_when_prettier_does_not_set_a_line_length(
    run_line_length: RunLineLength, fail: MakeFinding
) -> None:
    result = run_line_length({"ruff.toml": RUFF_120, "prettier.config.ts": "export default {};\n"})
    assert result.findings == [fail("prettier.config.ts does not set printWidth = 120")]


def test_12_4_1_passes_when_ruff_and_prettier_both_match_the_standard(
    run_line_length: RunLineLength, ok: MakeFinding
) -> None:
    result = run_line_length({"ruff.toml": RUFF_120, "prettier.config.ts": PRETTIER_120})
    assert result.findings == [ok("ruff and prettier both wrap at 120")]
