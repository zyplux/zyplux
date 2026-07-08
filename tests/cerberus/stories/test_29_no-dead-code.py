from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Finding, Status

type RunCheckWithFiles = Callable[[str, dict[str, str]], CheckResult]

CHECK_ID = "no-dead-code"

_PACKAGE_JSON = '{"name": "demo"}'


class ProcDouble(Protocol):
    """The shape of the subprocess test double `fake_proc` hands back.

    A structural type, not a nominal import of the concrete class conftest.py
    builds — keeps this file free of any dependency on where that class lives.
    """

    calls: list[tuple[list[str], Path | None]]

    def serve(self, tool: str, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None: ...
    def serve_missing(self, tool: str) -> None: ...


def test_29_1_1_skips_repos_with_no_package_json_without_running_fallow(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    result = run_check_with_files(CHECK_ID, {})
    assert result.findings == [finding(status.SKIP, "no package.json")]
    assert fake_proc.calls == []


def test_29_2_1_passes_when_fallow_dead_code_exits_clean(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("fallow")
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [finding(status.PASS, "fallow found no dead code or circular dependencies")]


def test_29_2_2_runs_fallow_dead_code_non_interactively_at_the_repo_root(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble
) -> None:
    fake_proc.serve("fallow")
    run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert fake_proc.calls == [(["bunx", "fallow", "dead-code", "--quiet", "--fail-on-issues"], Path())]


def test_29_2_3_fails_when_fallow_dead_code_reports_issues(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("fallow", returncode=1, stdout="unused export foo in src/bar.ts\n")
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [
        finding(status.FAIL, "fallow found dead code (exit 1); run `bunx fallow dead-code` locally for details")
    ]


def test_29_2_4_errors_when_bunx_is_not_on_path(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve_missing("bunx")
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [finding(status.ERROR, "`bunx` not found on PATH")]
