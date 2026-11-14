from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult
    from seam_fixtures import MakeFinding, RunCheckWithFiles

type RunPnpmReleaseAge = Callable[[str | None], CheckResult]

CHECK_ID = "pnpm_release_age"

POLICY = """minimumReleaseAge: 1440
minimumReleaseAgeExcludePrune: true
minimumReleaseAgeExclude:
  - '@zyplux/*'
"""


@pytest.fixture
def run_pnpm_release_age(run_check_with_files: RunCheckWithFiles) -> RunPnpmReleaseAge:
    def run(workspace: str | None) -> CheckResult:
        files = {} if workspace is None else {"pnpm-workspace.yaml": workspace}
        return run_check_with_files(CHECK_ID, files)

    return run


def test_32_1_1_skips_repos_without_a_pnpm_workspace(
    run_pnpm_release_age: RunPnpmReleaseAge, skip: MakeFinding
) -> None:
    assert run_pnpm_release_age(None).findings == [skip("not a pnpm workspace")]


def test_32_2_1_accepts_the_release_age_policy(run_pnpm_release_age: RunPnpmReleaseAge, ok: MakeFinding) -> None:
    assert run_pnpm_release_age(POLICY).findings == [ok("pnpm release-age policy is enforced")]


def test_32_2_2_requires_a_one_day_quarantine(run_pnpm_release_age: RunPnpmReleaseAge, fail: MakeFinding) -> None:
    result = run_pnpm_release_age(POLICY.replace("1440", "60"))
    assert result.findings == [fail("minimumReleaseAge must be 1440 minutes")]


def test_32_2_3_requires_stale_exclusion_pruning(run_pnpm_release_age: RunPnpmReleaseAge, fail: MakeFinding) -> None:
    result = run_pnpm_release_age(POLICY.replace("minimumReleaseAgeExcludePrune: true\n", ""))
    assert result.findings == [fail("minimumReleaseAgeExcludePrune must be true")]


def test_32_2_4_rejects_external_package_exclusions(run_pnpm_release_age: RunPnpmReleaseAge, fail: MakeFinding) -> None:
    result = run_pnpm_release_age(POLICY.replace("  - '@zyplux/*'", "  - vite"))
    assert result.findings == [fail("minimumReleaseAgeExclude permits only @zyplux/* packages: vite")]


def test_32_2_5_accepts_no_exclusions(run_pnpm_release_age: RunPnpmReleaseAge, ok: MakeFinding) -> None:
    workspace = POLICY.replace("minimumReleaseAgeExclude:\n  - '@zyplux/*'\n", "")
    assert run_pnpm_release_age(workspace).findings == [ok("pnpm release-age policy is enforced")]


def test_32_3_1_errors_on_invalid_yaml(run_pnpm_release_age: RunPnpmReleaseAge, error: MakeFinding) -> None:
    result = run_pnpm_release_age("minimumReleaseAge: [")
    assert result.findings == [error("pnpm-workspace.yaml is not valid YAML")]
