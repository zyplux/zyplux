from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from seam_fixtures import FakeProc, MakeFinding, RunCheckOnDisk, RunCheckWithFiles

CHECK_ID = "release_surface_version_bump"
DONE = "every published target's version tracks its surface"


def test_14_1_1_skips_repos_that_publish_nothing(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, skip: MakeFinding
) -> None:
    result = run_check_with_files(CHECK_ID, {})
    assert result.findings == [skip("no airlock-targets.toml — repo publishes nothing")]
    assert fake_proc.calls == []


def test_14_2_1_checks_the_repository_without_an_npm_cli(
    run_check_on_disk: RunCheckOnDisk, fake_proc: FakeProc, ok: MakeFinding
) -> None:
    result = run_check_on_disk(CHECK_ID, {"airlock-targets.toml": 'scope = "@zyplux"'})
    assert result.findings == [ok(DONE)]
    assert fake_proc.calls == []


@pytest.mark.parametrize("manifest", ["invalid = toml = text", "", 'scope = ""'])
def test_14_2_2_reports_manifest_errors_from_airlock(run_check_on_disk: RunCheckOnDisk, manifest: str) -> None:
    result = run_check_on_disk(CHECK_ID, {"airlock-targets.toml": manifest})
    assert len(result.problems) == 1
    assert result.problems[0].status.name == "ERROR"
    assert result.problems[0].message.startswith("cannot check release surfaces:")


def test_14_2_3_preserves_findings_from_multiple_targets(run_check_on_disk: RunCheckOnDisk) -> None:
    manifest = 'scope = "@zyplux"\n'
    names = ("first", "second")
    for name in names:
        manifest += f'[{name}]\nkind = "npm"\nsurface = []\nversion = {{ file = "{name}.json", json = "version" }}\n'
    result = run_check_on_disk(CHECK_ID, {"airlock-targets.toml": manifest})
    assert len(result.problems) == len(names)
    assert all(finding.status.name == "FAIL" for finding in result.findings)
    assert "@zyplux/first" in result.findings[0].message
    assert "@zyplux/second" in result.findings[1].message
