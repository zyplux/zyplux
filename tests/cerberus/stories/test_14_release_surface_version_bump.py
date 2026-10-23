from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from cerberus.context import Context
    from seam_fixtures import FakeProc, MakeFinding, RunCheckWithFiles

CHECK_ID = "release_surface_version_bump"
MANIFEST = {"airlock-targets.toml": 'scope = "@zyplux"'}
DONE = "every published target's version tracks its surface"


def test_14_1_1_skips_repos_that_publish_nothing(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, skip: MakeFinding
) -> None:
    result = run_check_with_files(CHECK_ID, {})

    assert result.findings == [skip("no airlock-targets.toml — repo publishes nothing")]
    assert fake_proc.calls == []


def test_14_2_1_runs_the_installed_airlock_in_the_repository(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, ctx: Context, ok: MakeFinding
) -> None:
    fake_proc.serve("pnpm exec", stdout=json.dumps([{"status": "pass", "message": DONE}]))

    result = run_check_with_files(CHECK_ID, MANIFEST)

    assert result.findings == [ok(DONE)]
    assert fake_proc.calls == [(["pnpm", "exec", "airlock", "check-surface", "--json"], ctx.source.root)]


@pytest.mark.parametrize("status", ["pass", "skip", "fail", "error"])
def test_14_2_2_reports_airlock_findings_without_reinterpreting_release_policy(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, status: str
) -> None:
    message = "@zyplux/widget: release validation finding"
    fake_proc.serve("pnpm exec", stdout=json.dumps([{"status": status, "message": message}]))

    result = run_check_with_files(CHECK_ID, {"airlock-targets.toml": "Airlock owns manifest parsing"})

    assert len(result.findings) == 1
    assert result.findings[0].status.name.lower() == status
    assert result.findings[0].message == message


def test_14_2_3_preserves_findings_from_multiple_targets(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, ok: MakeFinding, fail: MakeFinding
) -> None:
    fake_proc.serve(
        "pnpm exec",
        returncode=1,
        stdout=json.dumps([
            {"status": "pass", "message": "first target is prepared"},
            {"status": "fail", "message": "second target needs a bump"},
        ]),
    )

    result = run_check_with_files(CHECK_ID, MANIFEST)

    assert result.findings == [ok("first target is prepared"), fail("second target needs a bump")]


def test_14_3_1_errors_when_pnpm_is_missing(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, error: MakeFinding
) -> None:
    fake_proc.serve_missing("pnpm")

    result = run_check_with_files(CHECK_ID, MANIFEST)

    assert result.findings == [error("`pnpm` not found on PATH")]


def test_14_3_2_reports_an_unavailable_airlock_command(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, error: MakeFinding
) -> None:
    fake_proc.serve("pnpm exec", returncode=1, stderr="Command airlock not found")

    result = run_check_with_files(CHECK_ID, MANIFEST)

    assert result.findings == [error("Airlock returned invalid findings: Command airlock not found")]


def test_14_3_3_rejects_a_failed_command_even_if_its_findings_pass(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, ok: MakeFinding, error: MakeFinding
) -> None:
    fake_proc.serve(
        "pnpm exec",
        returncode=2,
        stdout=json.dumps([{"status": "pass", "message": DONE}]),
        stderr="Airlock failed after reporting",
    )

    result = run_check_with_files(CHECK_ID, MANIFEST)

    assert result.findings == [ok(DONE), error("Airlock exited 2: Airlock failed after reporting")]


def test_14_3_4_reports_a_failed_command_without_stderr(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, error: MakeFinding
) -> None:
    fake_proc.serve("pnpm exec", returncode=1, stdout=json.dumps([{"status": "pass", "message": DONE}]))

    result = run_check_with_files(CHECK_ID, MANIFEST)

    assert result.findings[-1] == error("Airlock exited 1: release validation failed")


def test_14_3_5_preserves_command_errors_written_to_stdout(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, error: MakeFinding
) -> None:
    fake_proc.serve("pnpm exec", returncode=1, stdout="Command airlock not found")

    result = run_check_with_files(CHECK_ID, MANIFEST)

    assert result.findings == [error("Airlock returned invalid findings: Command airlock not found")]


@pytest.mark.parametrize(
    "stdout",
    [
        "null",
        "{}",
        "[]",
        "[null]",
        "[{}]",
        '[{"status":"unknown","message":"finding"}]',
        '[{"status":1,"message":"finding"}]',
        '[{"status":"pass","message":null}]',
        '[{"status":"pass","message":" "}]',
        "not json",
    ],
)
def test_14_4_1_rejects_malformed_structured_findings(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, stdout: str, error: MakeFinding
) -> None:
    fake_proc.serve("pnpm exec", stdout=stdout)

    result = run_check_with_files(CHECK_ID, MANIFEST)

    assert len(result.problems) == 1
    assert result.problems[0].status == error("").status
    assert result.problems[0].message.startswith("Airlock returned invalid findings:")
