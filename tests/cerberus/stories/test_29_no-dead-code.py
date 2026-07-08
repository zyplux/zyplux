from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Finding, Status

type RunCheckWithFiles = Callable[[str, dict[str, str]], CheckResult]

CHECK_ID = "no-dead-code"

_PACKAGE_JSON = '{"name": "demo"}'

_DEAD_CODE_ARGV = ["bunx", "fallow", "dead-code", "--quiet", "--fail-on-issues", "--format", "json"]
_HEALTH_ARGV = ["bunx", "fallow", "health", "--quiet", "--fail-on-issues", "--format", "json"]

_CLEAN_DEAD_CODE = json.dumps({"total_issues": 0})
_CLEAN_HEALTH = json.dumps({"findings": [], "summary": {}})
_HEALTH_OVER_THRESHOLD = json.dumps(
    {
        "findings": [
            {
                "path": "src/rules/params.ts",
                "name": "planParameter",
                "line": 144,
                "cyclomatic": 25,
                "cognitive": 30,
                "crap": 160.0,
            },
            {
                "path": "src/rules/types.ts",
                "name": "checkParams",
                "line": 292,
                "cyclomatic": 13,
                "cognitive": 16,
                "crap": 49.5,
            },
        ],
        "summary": {
            "max_cyclomatic_threshold": 20,
            "max_cognitive_threshold": 15,
            "max_crap_threshold": 30.0,
        },
    }
)


class ProcDouble(Protocol):
    """The shape of the subprocess test double `fake_proc` hands back.

    A structural type, not a nominal import of the concrete class conftest.py
    builds — keeps this file free of any dependency on where that class lives.
    """

    calls: list[tuple[list[str], Path | None]]

    def serve(
        self,
        tool: str,
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        output_files: dict[str, str] | None = None,
    ) -> None: ...
    def serve_missing(self, tool: str) -> None: ...


def _serve_clean(fake_proc: ProcDouble) -> None:
    fake_proc.serve("fallow dead-code", stdout=_CLEAN_DEAD_CODE)
    fake_proc.serve("fallow health", stdout=_CLEAN_HEALTH)


def test_29_1_1_skips_repos_with_no_package_json_without_running_fallow(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    result = run_check_with_files(CHECK_ID, {})
    assert result.findings == [finding(status.SKIP, "no package.json")]
    assert fake_proc.calls == []


def test_29_2_1_passes_when_both_fallow_analyses_exit_clean(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    _serve_clean(fake_proc)
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [
        finding(status.PASS, "fallow found no dead code, cycles, or complexity offenders")
    ]


def test_29_2_2_runs_fallow_dead_code_and_health_non_interactively_at_the_repo_root(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble
) -> None:
    _serve_clean(fake_proc)
    run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert fake_proc.calls == [(_DEAD_CODE_ARGV, Path()), (_HEALTH_ARGV, Path())]


def test_29_2_3_fails_with_the_issue_count_when_fallow_dead_code_reports_issues(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("fallow dead-code", returncode=1, stdout=json.dumps({"total_issues": 3}))
    fake_proc.serve("fallow health", stdout=_CLEAN_HEALTH)
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [
        finding(
            status.FAIL, "fallow found 3 dead-code issues; run `bunx fallow dead-code` locally for details"
        )
    ]


def test_29_2_4_errors_when_bunx_is_not_on_path(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve_missing("bunx")
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [finding(status.ERROR, "`bunx` not found on PATH")]


def test_29_3_1_fails_listing_each_function_fallow_health_flags_above_its_thresholds(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("fallow dead-code", stdout=_CLEAN_DEAD_CODE)
    fake_proc.serve("fallow health", returncode=1, stdout=_HEALTH_OVER_THRESHOLD)
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [
        finding(
            status.FAIL,
            "fallow found 2 functions above its complexity thresholds\n"
            "    src/rules/params.ts:144 planParameter — cyclomatic 25/20, cognitive 30/15, CRAP 160/30\n"
            "    src/rules/types.ts:292 checkParams — cyclomatic 13/20, cognitive 16/15, CRAP 49.5/30",
        )
    ]


def test_29_4_1_reports_the_combined_fallow_issue_count(
    run_check_with_files: RunCheckWithFiles, fake_proc: ProcDouble
) -> None:
    fake_proc.serve("fallow dead-code", returncode=1, stdout=json.dumps({"total_issues": 3}))
    fake_proc.serve("fallow health", returncode=1, stdout=_HEALTH_OVER_THRESHOLD)
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.detail == "ts: 5"
