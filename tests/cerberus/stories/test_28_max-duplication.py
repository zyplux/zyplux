from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.context import Context
    from cerberus.model import CheckResult, Finding, Repo, Status

type RunCheck = Callable[[str, Repo, Context], CheckResult]
type MakeContext = Callable[..., Context]
type RunMaxDuplication = Callable[..., CheckResult]

CHECK_ID = "max-duplication"

_CUSTOM_THRESHOLD_TOML = 'default_recipe_marker = "just --list"\n\n[max_duplication]\nthreshold = 5\n'
_THRESHOLDLESS_TOML = 'default_recipe_marker = "just --list"\n\n[max_duplication]\npattern = "**/*.py"\n'
_CUSTOM_SELECTION_TOML = (
    'default_recipe_marker = "just --list"\n\n'
    "[max_duplication]\n"
    'pattern = "**/*.rs"\n'
    'ignore = ["**/target/**"]\n'
)
_DEFAULT_PATTERN = "**/*.{ts,tsx,py}"
_DEFAULT_IGNORE = (
    "**/node_modules/**,**/dist/**,**/.venv/**,**/coverage/**,**/reference_clones/**,**/graphify-out/**"
)
_REPORT_DIR_PLACEHOLDER = "<report-dir>"


def _clone(first: str, second: str) -> dict[str, object]:
    def _file(name: str, start: int, end: int) -> dict[str, object]:
        return {"name": name, "startLoc": {"line": start, "column": 1}, "endLoc": {"line": end, "column": 9}}

    return {"firstFile": _file(first, 4, 24), "secondFile": _file(second, 40, 60)}


def _report(
    clones: list[dict[str, object]] | None = None, **percentages_by_format: tuple[int, float]
) -> dict[str, str]:
    formats = {
        fmt: {"total": {"duplicatedTokens": tokens, "percentageTokens": percentage}}
        for fmt, (tokens, percentage) in percentages_by_format.items()
    }
    return {
        "jscpd-report.json": json.dumps({"duplicates": clones or [], "statistics": {"formats": formats}})
    }


_UNDER_THRESHOLD_REPORT = _report(typescript=(1167, 1.9), python=(1623, 1.3))
_LANGUAGE_OVER_THRESHOLD_REPORT = _report(
    clones=[_clone("src/a.ts", "src/b.ts")], typescript=(1167, 3.1), python=(120, 0.2)
)


def _argv(pattern: str = _DEFAULT_PATTERN, ignore: str = _DEFAULT_IGNORE) -> list[str]:
    return [
        "bunx",
        "jscpd",
        "--pattern",
        pattern,
        "--ignore",
        ignore,
        "--reporters",
        "json",
        "--silent",
        "--output",
        _REPORT_DIR_PLACEHOLDER,
        ".",
    ]


def _mask_report_dir(calls: list[tuple[list[str], Path | None]]) -> list[tuple[list[str], Path | None]]:
    masked = []
    for argv, cwd in calls:
        argv = list(argv)
        report_dir_idx = argv.index("--output") + 1
        argv[report_dir_idx] = _REPORT_DIR_PLACEHOLDER
        masked.append((argv, cwd))
    return masked


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


@pytest.fixture
def run_max_duplication(
    repo: Repo, ctx: Context, run_check: RunCheck, make_context: MakeContext, tmp_path: Path
) -> RunMaxDuplication:
    def _run(*, config_toml: str | None = None) -> CheckResult:
        if config_toml is None:
            return run_check(CHECK_ID, repo, ctx)
        config_path = tmp_path / "cerberus.toml"
        config_path.write_text(config_toml)
        return run_check(CHECK_ID, repo, make_context(Path(), config_path=config_path))

    return _run


def test_28_1_1_passes_when_every_language_stays_under_the_duplication_threshold(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd", output_files=_UNDER_THRESHOLD_REPORT)
    result = run_max_duplication()
    assert result.findings == [finding(status.PASS, "duplication is under the 2% threshold in every language")]


def test_28_1_2_fails_when_one_language_exceeds_the_threshold_even_though_the_total_is_under(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd", output_files=_LANGUAGE_OVER_THRESHOLD_REPORT)
    result = run_max_duplication()
    assert result.findings == [
        finding(
            status.FAIL,
            "duplication exceeds the 2% threshold in ts\n    src/a.ts [4:1 - 24:9] duplicates src/b.ts [40:1 - 60:9]",
        )
    ]


def test_28_1_3_fails_with_the_exit_code_when_jscpd_itself_exits_non_zero(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd", returncode=3)
    result = run_max_duplication()
    assert result.findings == [
        finding(
            status.FAIL,
            f"jscpd exited 3; run `bunx jscpd --pattern {_DEFAULT_PATTERN} --ignore {_DEFAULT_IGNORE} .`"
            " locally for details",
        )
    ]


def test_28_1_4_errors_when_bunx_is_not_on_path(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve_missing("bunx")
    result = run_max_duplication()
    assert result.findings == [finding(status.ERROR, "`bunx` not found on PATH")]


def test_28_1_5_errors_when_jscpd_writes_no_readable_json_report(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd")
    result = run_max_duplication()
    assert result.findings == [finding(status.ERROR, "jscpd wrote no readable json report")]


def test_28_2_1_reports_duplicated_tokens_and_percentage_per_language(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble
) -> None:
    fake_proc.serve("jscpd", output_files=_report(typescript=(1167, 2.2), python=(1623, 1.3)))
    result = run_max_duplication()
    assert result.detail == "ts: 1167 (2.20%); py: 1623 (1.30%)"


def test_28_2_2_reads_reports_with_flat_per_language_stats(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble
) -> None:
    flat = {"typescript": {"duplicatedTokens": 40, "percentageTokens": 0.5}}
    report = {"jscpd-report.json": json.dumps({"duplicates": [], "statistics": {"formats": flat}})}
    fake_proc.serve("jscpd", output_files=report)
    result = run_max_duplication()
    assert result.detail == "ts: 40 (0.50%)"


def test_28_3_1_runs_jscpd_at_the_repo_root_with_the_default_selection(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble
) -> None:
    fake_proc.serve("jscpd", output_files=_UNDER_THRESHOLD_REPORT)
    run_max_duplication()
    assert _mask_report_dir(fake_proc.calls) == [(_argv(), Path())]


def test_28_3_2_enforces_a_configured_threshold_per_language(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd", output_files=_LANGUAGE_OVER_THRESHOLD_REPORT)
    result = run_max_duplication(config_toml=_CUSTOM_THRESHOLD_TOML)
    assert result.findings == [finding(status.PASS, "duplication is under the 5% threshold in every language")]


def test_28_3_3_defaults_the_threshold_to_two_percent_when_the_config_omits_it(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd", output_files=_LANGUAGE_OVER_THRESHOLD_REPORT)
    result = run_max_duplication(config_toml=_THRESHOLDLESS_TOML)
    assert result.findings[0].status == status.FAIL
    assert result.findings[0].message.startswith("duplication exceeds the 2% threshold in ts")


def test_28_3_4_passes_a_configured_pattern_and_ignore_through_to_jscpd(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble
) -> None:
    fake_proc.serve("jscpd", output_files=_UNDER_THRESHOLD_REPORT)
    run_max_duplication(config_toml=_CUSTOM_SELECTION_TOML)
    assert _mask_report_dir(fake_proc.calls) == [(_argv(pattern="**/*.rs", ignore="**/target/**"), Path())]
