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
type RunJscpdDupes = Callable[..., CheckResult]

CHECK_ID = "jscpd_dupes_threshold"

_CUSTOM_THRESHOLD_TOML = 'default_recipe_marker = "just --list"\n\n[jscpd_dupes_threshold]\nthreshold = 5\n'
_THRESHOLDLESS_TOML = 'default_recipe_marker = "just --list"\n\n[jscpd_dupes_threshold]\npattern = "**/*.py"\n'
_CUSTOM_SELECTION_TOML = (
    'default_recipe_marker = "just --list"\n\n[jscpd_dupes_threshold]\npattern = "**/*.rs"\nignore = ["**/target/**"]\n'
)
_DEFAULT_PATTERN = "**/*.{ts,tsx,py}"
_DEFAULT_IGNORE = "**/dist/**,**/.venv/**,**/*.gen.*"
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
    return {"jscpd-report.json": json.dumps({"duplicates": clones or [], "statistics": {"formats": formats}})}


_UNDER_THRESHOLD_REPORT = _report(typescript=(1167, 1.9), python=(1623, 1.3))
_LANGUAGE_OVER_THRESHOLD_REPORT = _report(
    clones=[_clone("src/a.ts", "src/b.ts")], typescript=(1167, 3.1), python=(120, 0.2)
)


def _argv(scan_roots: list[str], pattern: str = _DEFAULT_PATTERN, ignore: str = _DEFAULT_IGNORE) -> list[str]:
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
        "--absolute",
        "--output",
        _REPORT_DIR_PLACEHOLDER,
        *scan_roots,
    ]


def _mask_report_dir(calls: list[tuple[list[str], Path | None]]) -> list[tuple[list[str], Path | None]]:
    masked = []
    for argv, cwd in calls:
        masked_argv = list(argv)
        report_dir_idx = masked_argv.index("--output") + 1
        report_dir = masked_argv[report_dir_idx]
        masked_argv[report_dir_idx] = _REPORT_DIR_PLACEHOLDER
        masked_cwd = Path(_REPORT_DIR_PLACEHOLDER) if cwd == Path(report_dir) else cwd
        masked.append((masked_argv, masked_cwd))
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
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


@pytest.fixture
def run_jscpd_dupes(
    repo: Repo, run_check: RunCheck, make_context: MakeContext, tmp_path: Path, repo_root: Path
) -> RunJscpdDupes:
    def _run(*, config_toml: str | None = None, files: dict[str, str] | None = None) -> CheckResult:
        for path, content in (files or {}).items():
            target = repo_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        config_path = None
        if config_toml is not None:
            config_path = tmp_path / "cerberus.toml"
            config_path.write_text(config_toml)
        return run_check(CHECK_ID, repo, make_context(repo_root, config_path=config_path))

    return _run


def test_28_1_1_passes_when_every_language_stays_under_the_duplication_threshold(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd", output_files=_UNDER_THRESHOLD_REPORT)
    result = run_jscpd_dupes()
    assert result.findings == [finding(status.PASS, "duplication is under the 2% threshold in every language")]


def test_28_1_2_fails_when_one_language_exceeds_the_threshold_even_though_the_total_is_under(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd", output_files=_LANGUAGE_OVER_THRESHOLD_REPORT)
    result = run_jscpd_dupes()
    assert result.findings == [
        finding(
            status.FAIL,
            "ts: 1167 (3.10%); py: 120 (0.20%)\n    src/a.ts [4:1 - 24:9] duplicates src/b.ts [40:1 - 60:9]",
        )
    ]


def test_28_1_3_fails_with_the_exit_code_when_jscpd_itself_exits_non_zero(
    run_jscpd_dupes: RunJscpdDupes,
    fake_proc: ProcDouble,
    finding: type[Finding],
    status: type[Status],
    repo_root: Path,
) -> None:
    fake_proc.serve("jscpd", returncode=3)
    result = run_jscpd_dupes()
    assert result.findings == [
        finding(
            status.FAIL,
            f"jscpd exited 3; run `bunx jscpd --pattern {_DEFAULT_PATTERN} --ignore {_DEFAULT_IGNORE}"
            f" {repo_root.resolve()}` locally for details",
        )
    ]


def test_28_1_4_errors_when_bunx_is_not_on_path(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve_missing("bunx")
    result = run_jscpd_dupes()
    assert result.findings == [finding(status.ERROR, "`bunx` not found on PATH")]


def test_28_1_5_errors_when_jscpd_writes_no_readable_json_report(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd")
    result = run_jscpd_dupes()
    assert result.findings == [finding(status.ERROR, "jscpd wrote no readable json report")]


def test_28_2_1_reports_duplicated_tokens_and_percentage_per_language(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble
) -> None:
    fake_proc.serve("jscpd", output_files=_report(typescript=(1167, 1.9), python=(1623, 1.3)))
    result = run_jscpd_dupes()
    assert result.detail == "ts: 1167 (1.90%); py: 1623 (1.30%)"


def test_28_2_2_reads_reports_with_flat_per_language_stats(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble
) -> None:
    flat = {"typescript": {"duplicatedTokens": 40, "percentageTokens": 0.5}}
    report = {"jscpd-report.json": json.dumps({"duplicates": [], "statistics": {"formats": flat}})}
    fake_proc.serve("jscpd", output_files=report)
    result = run_jscpd_dupes()
    assert result.detail == "ts: 40 (0.50%)"


def test_28_2_3_leaves_the_detail_unset_on_failure_so_the_stats_appear_only_in_the_fail_line(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble
) -> None:
    fake_proc.serve("jscpd", output_files=_LANGUAGE_OVER_THRESHOLD_REPORT)
    result = run_jscpd_dupes()
    assert result.detail is None


def test_28_3_1_scans_the_repo_root_with_the_default_selection_and_cwd_shielded_from_repo_config(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble, repo_root: Path
) -> None:
    fake_proc.serve("jscpd", output_files=_UNDER_THRESHOLD_REPORT)
    run_jscpd_dupes()
    expected = (_argv([str(repo_root.resolve())]), Path(_REPORT_DIR_PLACEHOLDER))
    assert _mask_report_dir(fake_proc.calls) == [expected]


def test_28_3_2_enforces_a_configured_threshold_per_language(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd", output_files=_LANGUAGE_OVER_THRESHOLD_REPORT)
    result = run_jscpd_dupes(config_toml=_CUSTOM_THRESHOLD_TOML)
    assert result.findings == [finding(status.PASS, "duplication is under the 5% threshold in every language")]


def test_28_3_3_defaults_the_threshold_to_two_percent_when_the_config_omits_it(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble, status: type[Status]
) -> None:
    fake_proc.serve("jscpd", output_files=_LANGUAGE_OVER_THRESHOLD_REPORT)
    result = run_jscpd_dupes(config_toml=_THRESHOLDLESS_TOML)
    assert result.findings[0].status == status.FAIL
    assert result.findings[0].message.startswith("ts: 1167 (3.10%); py: 120 (0.20%)")


def test_28_3_4_passes_a_configured_pattern_and_ignore_through_to_jscpd(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble, repo_root: Path
) -> None:
    fake_proc.serve("jscpd", output_files=_UNDER_THRESHOLD_REPORT)
    run_jscpd_dupes(config_toml=_CUSTOM_SELECTION_TOML)
    expected = _argv([str(repo_root.resolve())], pattern="**/*.rs", ignore="**/target/**")
    assert _mask_report_dir(fake_proc.calls) == [(expected, Path(_REPORT_DIR_PLACEHOLDER))]


def test_28_4_1_scans_only_the_directories_the_workspace_manifests_register(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble, repo_root: Path
) -> None:
    fake_proc.serve("jscpd", output_files=_UNDER_THRESHOLD_REPORT)
    (repo_root / "apps" / "web").mkdir(parents=True)
    (repo_root / "libs" / "py").mkdir(parents=True)
    (repo_root / "docs" / "scratch").mkdir(parents=True)
    run_jscpd_dupes(
        files={
            "package.json": json.dumps({"workspaces": {"packages": ["apps/*"]}}),
            "pyproject.toml": '[tool.uv.workspace]\nmembers = ["libs/py"]\n',
        }
    )
    root = repo_root.resolve()
    expected_roots = [str(root / "apps" / "web"), str(root / "libs" / "py")]
    assert _mask_report_dir(fake_proc.calls) == [(_argv(expected_roots), Path(_REPORT_DIR_PLACEHOLDER))]


def test_28_4_2_falls_back_to_the_repo_root_when_no_manifest_declares_workspaces(
    run_jscpd_dupes: RunJscpdDupes, fake_proc: ProcDouble, repo_root: Path
) -> None:
    fake_proc.serve("jscpd", output_files=_UNDER_THRESHOLD_REPORT)
    run_jscpd_dupes(files={"package.json": json.dumps({"name": "demo"})})
    assert _mask_report_dir(fake_proc.calls) == [(_argv([str(repo_root.resolve())]), Path(_REPORT_DIR_PLACEHOLDER))]
