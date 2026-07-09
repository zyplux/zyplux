from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from cerberus.model import CheckResult
    from seam_fixtures import MakeFinding, RunCheckOnDisk, RunCheckWithFiles

type RunRumdl = Callable[[str | None], CheckResult]

CHECK_ID = "rumdl-config"

NON_CANONICAL = '[global]\ndisable = ["MD033", "MD013"]\n\n[MD024]\nsiblings-only = true\n'
UNPARSEABLE = "[global\ndisable = [\n"

FIXED_WITH_EXCLUDE = (
    "[global]\n"
    'exclude = ["reference_clones"]\n'
    "disable = [\n"
    '    "MD013", # line-length\n'
    '    "MD022", # blanks-around-headings\n'
    '    "MD031", # blanks-around-fences\n'
    '    "MD032", # blanks-around-lists\n'
    '    "MD033", # no-inline-html\n'
    "]\n"
    "\n"
    "# no-duplicate-heading\n"
    "[MD024]\n"
    "siblings-only = true\n"
)


@pytest.fixture
def run_rumdl(run_check_with_files: RunCheckWithFiles) -> RunRumdl:
    def run(content: str | None) -> CheckResult:
        files = {} if content is None else {".rumdl.toml": content}
        return run_check_with_files(CHECK_ID, files)

    return run


def test_5_1_1_passes_when_the_config_matches_canonical(
    run_rumdl: RunRumdl, rumdl_canonical: str, ok: MakeFinding
) -> None:
    result = run_rumdl(rumdl_canonical)
    assert result.findings == [ok(".rumdl.toml matches the org canonical")]


def test_5_1_2_passes_when_a_repo_specific_exclude_list_is_set(
    run_rumdl: RunRumdl, rumdl_canonical: str, ok: MakeFinding
) -> None:
    content = rumdl_canonical.replace("]\n", ']\nexclude = ["reference_clones"]\n', 1)
    result = run_rumdl(content)
    assert result.findings == [ok(".rumdl.toml matches the org canonical")]


def test_5_1_3_fails_when_the_rule_config_differs_from_canonical(run_rumdl: RunRumdl, fail: MakeFinding) -> None:
    result = run_rumdl(NON_CANONICAL)
    assert result.findings == [fail(".rumdl.toml rule config does not match the org canonical")]


def test_5_1_4_fails_when_no_config_file_exists(run_rumdl: RunRumdl, fail: MakeFinding) -> None:
    result = run_rumdl(None)
    assert result.findings == [fail("no .rumdl.toml at repo root")]


def test_5_1_5_errors_when_the_config_cannot_be_parsed(run_rumdl: RunRumdl, error: MakeFinding) -> None:
    result = run_rumdl(UNPARSEABLE)
    assert result.findings == [
        error(
            "could not parse .rumdl.toml: Expected ']' at the end of a table declaration (at line 1, column 8)",
        )
    ]


def test_5_2_1_creates_a_canonical_config_when_none_exists(
    run_check_on_disk: RunCheckOnDisk, tmp_path: Path, rumdl_canonical: str
) -> None:
    run_check_on_disk(CHECK_ID, {}, fix=True)
    assert (tmp_path / ".rumdl.toml").read_text() == rumdl_canonical


@pytest.fixture
def fixed_rumdl_toml(run_check_on_disk: RunCheckOnDisk, tmp_path: Path) -> Path:
    content = (
        '[global]\ndisable = ["MD033", "MD013"]\nexclude = ["reference_clones"]\n\n[MD024]\nsiblings-only = true\n'
    )
    run_check_on_disk(CHECK_ID, {".rumdl.toml": content}, fix=True)
    return tmp_path / ".rumdl.toml"


def test_5_2_2_rewrites_a_non_canonical_config_to_canonical_form_preserving_exclude(fixed_rumdl_toml: Path) -> None:
    assert fixed_rumdl_toml.read_text(encoding="utf-8") == FIXED_WITH_EXCLUDE


def test_5_2_3_rewrites_a_non_canonical_config_without_an_exclude_to_the_exact_canonical_text(
    run_check_on_disk: RunCheckOnDisk, tmp_path: Path, rumdl_canonical: str
) -> None:
    run_check_on_disk(CHECK_ID, {".rumdl.toml": NON_CANONICAL}, fix=True)
    assert (tmp_path / ".rumdl.toml").read_text() == rumdl_canonical


def test_5_2_4_passes_when_re_checked_after_being_fixed(
    fixed_rumdl_toml: Path, run_check_on_disk: RunCheckOnDisk, ok: MakeFinding
) -> None:
    del fixed_rumdl_toml
    result = run_check_on_disk(CHECK_ID, {}, fix=False)
    assert result.findings == [ok(".rumdl.toml matches the org canonical")]
