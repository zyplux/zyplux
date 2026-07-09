from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult
    from seam_fixtures import MakeFinding, RunCheckWithFiles

type RunCodeowners = Callable[[str | None], CheckResult]

CHECK_ID = "codeowners_coverage"

COVERS_GITHUB = "/.github/ @zyplux/admins\n"
WILDCARD_COVERS_EVERYTHING = "* @zyplux/admins\n"
LOOKALIKE_GITHUB_PATH = "docs/.github-notes @zyplux/admins\n"
NO_OWNERSHIP_RULES = "# just a header comment\n\n"


@pytest.fixture
def run_codeowners(run_check_with_files: RunCheckWithFiles) -> RunCodeowners:
    def run(content: str | None) -> CheckResult:
        files = {} if content is None else {".github/CODEOWNERS": content}
        return run_check_with_files(CHECK_ID, files)

    return run


def test_2_1_1_fails_when_no_codeowners_file_exists_in_any_recognized_location(
    run_codeowners: RunCodeowners, fail: MakeFinding
) -> None:
    result = run_codeowners(None)
    assert result.findings == [fail("no CODEOWNERS file")]


def test_2_1_2_passes_when_the_codeowners_file_exists_in_an_alternate_recognized_location(
    run_check_with_files: RunCheckWithFiles, ok: MakeFinding
) -> None:
    result = run_check_with_files(CHECK_ID, {"docs/CODEOWNERS": COVERS_GITHUB})
    assert result.findings == [ok("CODEOWNERS present, covers /.github/")]


def test_2_1_3_fails_when_the_codeowners_file_has_no_ownership_rules(
    run_codeowners: RunCodeowners, fail: MakeFinding
) -> None:
    result = run_codeowners(NO_OWNERSHIP_RULES)
    assert result.findings == [fail("CODEOWNERS has no ownership rules")]


def test_2_2_1_passes_when_a_rule_explicitly_owns_the_github_directory(
    run_codeowners: RunCodeowners, ok: MakeFinding
) -> None:
    result = run_codeowners(COVERS_GITHUB)
    assert result.findings == [ok("CODEOWNERS present, covers /.github/")]


def test_2_2_2_passes_when_a_wildcard_rule_owns_everything(run_codeowners: RunCodeowners, ok: MakeFinding) -> None:
    result = run_codeowners(WILDCARD_COVERS_EVERYTHING)
    assert result.findings == [ok("CODEOWNERS present, covers /.github/")]


def test_2_2_3_fails_when_only_a_lookalike_github_path_is_owned(
    run_codeowners: RunCodeowners, fail: MakeFinding
) -> None:
    result = run_codeowners(LOOKALIKE_GITHUB_PATH)
    assert result.findings == [fail("CODEOWNERS does not cover `/.github/`")]
