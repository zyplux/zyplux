from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Repo, Status
    from seam_fixtures import FakeProc, MakeContext, MakeFinding, NpmToolSpec, RunCheck, RunCheckWithFiles

type RunFallow = Callable[..., CheckResult]

CHECK_ID = "fallow"

_PACKAGE_JSON = '{"name": "demo"}'

_SHARED_FLAGS = ["--quiet", "--fail-on-issues", "--format", "json"]
_SHIELD_DIR_PLACEHOLDER = "<shield-dir>"

_CLEAN_DEAD_CODE = json.dumps({
    "kind": "dead-code",
    "schema_version": 7,
    "version": "3.3.0",
    "total_issues": 0,
})
_CLEAN_HEALTH = json.dumps({
    "kind": "health",
    "schema_version": 7,
    "version": "3.3.0",
    "elapsed_ms": 9,
    "findings": [],
    "summary": {
        "functions_analyzed": 941,
        "functions_above_threshold": 0,
        "average_maintainability": 92.1,
    },
})
_CLEAN_HEALTH_STATUS = "✓ 0 above threshold · 941 analyzed · maintainability 92.1 (good) (0.01s)"
_HEALTH_OVER_THRESHOLD = json.dumps({
    "kind": "health",
    "schema_version": 7,
    "version": "3.3.0",
    "elapsed_ms": 9,
    "findings": [
        {
            "path": "src/rules/params.ts",
            "name": "planParameter",
            "line": 144,
            "col": 21,
            "cyclomatic": 25,
            "cognitive": 30,
            "crap": 160.0,
        },
        {
            "path": "src/rules/types.ts",
            "name": "checkParams",
            "line": 292,
            "col": 17,
            "cyclomatic": 13,
            "cognitive": 16,
            "crap": 49.5,
        },
    ],
    "summary": {
        "functions_analyzed": 941,
        "functions_above_threshold": 2,
        "average_maintainability": 92.1,
        "max_cyclomatic_threshold": 20,
        "max_cognitive_threshold": 15,
        "max_crap_threshold": 30.0,
    },
})


def _serve_clean(fake_proc: FakeProc) -> None:
    fake_proc.serve("fallow dead-code")
    fake_proc.serve_report_file("fallow dead-code", _CLEAN_DEAD_CODE)
    fake_proc.serve("fallow health")
    fake_proc.serve_report_file("fallow health", _CLEAN_HEALTH)


def _argv(spec: str, analysis: str, repo_root: Path) -> list[str]:
    return [
        "bunx",
        spec,
        analysis,
        *_SHARED_FLAGS,
        "--root",
        str(repo_root.resolve()),
        "--config",
        f"{_SHIELD_DIR_PLACEHOLDER}/fallow.json",
        "--output-file",
        f"{_SHIELD_DIR_PLACEHOLDER}/{analysis}-report.json",
    ]


def _mask_shield_dir(calls: list[tuple[list[str], Path | None]]) -> list[tuple[list[str], Path | None]]:
    masked = []
    for argv, cwd in calls:
        masked_argv = list(argv)
        config_idx = masked_argv.index("--config") + 1
        shield_dir = str(Path(masked_argv[config_idx]).parent)
        for flag in ("--config", "--output-file"):
            flag_idx = masked_argv.index(flag) + 1
            masked_argv[flag_idx] = masked_argv[flag_idx].replace(shield_dir, _SHIELD_DIR_PLACEHOLDER)
        masked_cwd = Path(_SHIELD_DIR_PLACEHOLDER) if cwd == Path(shield_dir) else cwd
        masked.append((masked_argv, masked_cwd))
    return masked


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


@pytest.fixture
def run_fallow(repo: Repo, run_check: RunCheck, make_context: MakeContext, repo_root: Path) -> RunFallow:
    def _run(files: dict[str, str], *, verbose: bool = False) -> CheckResult:
        for path, content in files.items():
            target = repo_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        return run_check(CHECK_ID, repo, make_context(repo_root, verbose=verbose))

    return _run


def test_29_1_1_skips_repos_with_no_package_json_without_running_fallow(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, skip: MakeFinding
) -> None:
    result = run_check_with_files(CHECK_ID, {})
    assert result.findings == [skip("no package.json")]
    assert fake_proc.calls == []


def test_29_2_1_passes_when_both_fallow_analyses_exit_clean(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, ok: MakeFinding
) -> None:
    _serve_clean(fake_proc)
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [ok("fallow found no dead code, cycles, or complexity offenders")]


def test_29_2_2_runs_fallow_dead_code_and_health_non_interactively_from_a_shielded_cwd_against_the_repo_root(
    run_fallow: RunFallow, fake_proc: FakeProc, repo_root: Path, npm_tool_spec: NpmToolSpec
) -> None:
    _serve_clean(fake_proc)
    run_fallow({"package.json": _PACKAGE_JSON})
    assert _mask_shield_dir(fake_proc.calls) == [
        (_argv(npm_tool_spec("fallow"), "dead-code", repo_root), Path(_SHIELD_DIR_PLACEHOLDER)),
        (_argv(npm_tool_spec("fallow"), "health", repo_root), Path(_SHIELD_DIR_PLACEHOLDER)),
    ]


def test_29_2_3_fails_with_the_issue_count_when_fallow_dead_code_reports_issues(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, npm_tool_spec: NpmToolSpec, fail: MakeFinding
) -> None:
    fake_proc.serve("fallow dead-code", returncode=1)
    fake_proc.serve_report_file("fallow dead-code", json.dumps({"total_issues": 3}))
    fake_proc.serve("fallow health")
    fake_proc.serve_report_file("fallow health", _CLEAN_HEALTH)
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [
        fail(f"fallow found 3 dead-code issues; run `bunx {npm_tool_spec('fallow')} dead-code` locally for details")
    ]


def test_29_2_4_errors_when_bunx_is_not_on_path(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, error: MakeFinding
) -> None:
    fake_proc.serve_missing("bunx")
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [error("`bunx` not found on PATH")]


def test_29_3_1_fails_listing_each_function_fallow_health_flags_above_its_thresholds(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, fail: MakeFinding
) -> None:
    fake_proc.serve("fallow dead-code")
    fake_proc.serve_report_file("fallow dead-code", _CLEAN_DEAD_CODE)
    fake_proc.serve("fallow health", returncode=1)
    fake_proc.serve_report_file("fallow health", _HEALTH_OVER_THRESHOLD)
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [
        fail(
            "✗ 2 above threshold · 941 analyzed · maintainability 92.1 (good) (0.01s)\n"
            "    src/rules/params.ts:144 planParameter — cyclomatic 25/20, cognitive 30/15, CRAP 160/30\n"
            "    src/rules/types.ts:292 checkParams — cyclomatic 13/20, cognitive 16/15, CRAP 49.5/30",
        )
    ]


def test_29_3_2_fails_listing_only_the_metrics_fallow_reported_when_coverage_data_is_absent(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, fail: MakeFinding
) -> None:
    health_without_crap = json.dumps({
        "findings": [
            {
                "path": "src/rules/params.ts",
                "name": "planParameter",
                "line": 144,
                "cyclomatic": 25,
                "cognitive": 30,
            },
        ],
        "summary": {
            "functions_analyzed": 500,
            "functions_above_threshold": 1,
            "average_maintainability": 70.0,
            "max_cyclomatic_threshold": 20,
            "max_cognitive_threshold": 15,
            "max_crap_threshold": 30.0,
        },
    })
    fake_proc.serve("fallow dead-code")
    fake_proc.serve_report_file("fallow dead-code", _CLEAN_DEAD_CODE)
    fake_proc.serve("fallow health", returncode=1)
    fake_proc.serve_report_file("fallow health", health_without_crap)
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [
        fail(
            "✗ 1 above threshold · 500 analyzed · maintainability 70.0 (moderate)\n"
            "    src/rules/params.ts:144 planParameter — cyclomatic 25/20, cognitive 30/15",
        )
    ]


def test_29_3_3_falls_back_to_the_rerun_hint_only_when_fallow_crashes_without_writing_a_report(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, npm_tool_spec: NpmToolSpec, fail: MakeFinding
) -> None:
    fake_proc.serve("fallow dead-code")
    fake_proc.serve_report_file("fallow dead-code", _CLEAN_DEAD_CODE)
    fake_proc.serve("fallow health", returncode=2, stderr="fallow: internal error")
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [
        fail(f"fallow health exited 2; run `bunx {npm_tool_spec('fallow')} health` locally for details")
    ]


def test_29_4_1_reports_fallows_health_status_line_on_a_clean_run(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc
) -> None:
    _serve_clean(fake_proc)
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.detail == _CLEAN_HEALTH_STATUS


def test_29_4_2_leaves_the_detail_unset_on_failure_so_the_status_line_appears_only_in_the_fail_line(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc
) -> None:
    fake_proc.serve("fallow dead-code", returncode=1)
    fake_proc.serve_report_file("fallow dead-code", json.dumps({"total_issues": 3}))
    fake_proc.serve("fallow health", returncode=1)
    fake_proc.serve_report_file("fallow health", _HEALTH_OVER_THRESHOLD)
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.detail is None


def test_29_5_1_shields_fallow_behind_a_cerberus_owned_config_ignoring_workspace_dirs_without_a_package_json(
    run_fallow: RunFallow, fake_proc: FakeProc, repo_root: Path
) -> None:
    _serve_clean(fake_proc)
    (repo_root / "apps" / "py").mkdir(parents=True)
    (repo_root / "apps" / "web").mkdir(parents=True)
    (repo_root / "apps" / "web" / "package.json").write_text('{"name": "web"}')
    (repo_root / "tests" / "py").mkdir(parents=True)

    run_fallow({"package.json": json.dumps({"name": "demo", "workspaces": ["apps/*", "tests/*"]})})

    expected_config = {"ignorePatterns": ["apps/py", "tests/py"], "duplicates": {"ignoreDefaults": False}}
    assert [json.loads(snapshot) for snapshot in fake_proc.config_snapshots] == [expected_config, expected_config]
    assert all(not cwd.is_relative_to(repo_root) for _, cwd in fake_proc.calls if cwd is not None)


def test_29_5_2_errors_when_package_json_is_not_valid_json_instead_of_crashing(
    run_fallow: RunFallow, fake_proc: FakeProc, status: type[Status]
) -> None:
    result = run_fallow({"package.json": "{not json"})
    assert result.findings[0].status == status.ERROR
    assert result.findings[0].message.startswith("package.json is not valid JSON:")
    assert fake_proc.calls == []


_DEAD_CODE_WITH_ISSUES = json.dumps({
    "total_issues": 2,
    "unused_files": [{"path": "src/orphan.ts"}],
    "unused_exports": [{"path": "src/lib.ts", "export_name": "unusedThing", "line": 2, "col": 13}],
})


def test_29_5_3_switches_off_fallows_default_duplicate_ignores_so_test_files_count(
    run_fallow: RunFallow, fake_proc: FakeProc
) -> None:
    _serve_clean(fake_proc)
    run_fallow({"package.json": _PACKAGE_JSON})
    snapshots = [json.loads(snapshot) for snapshot in fake_proc.config_snapshots]
    assert all(snapshot["duplicates"] == {"ignoreDefaults": False} for snapshot in snapshots)


def _run_dead_code(run_fallow: RunFallow, fake_proc: FakeProc, report_json: str, *, verbose: bool) -> CheckResult:
    fake_proc.serve("fallow dead-code", returncode=1)
    fake_proc.serve_report_file("fallow dead-code", report_json)
    fake_proc.serve("fallow health")
    fake_proc.serve_report_file("fallow health", _CLEAN_HEALTH)
    return run_fallow({"package.json": _PACKAGE_JSON}, verbose=verbose)


def _run_dead_code_with_issues(run_fallow: RunFallow, fake_proc: FakeProc, *, verbose: bool) -> CheckResult:
    return _run_dead_code(run_fallow, fake_proc, _DEAD_CODE_WITH_ISSUES, verbose=verbose)


def test_29_6_1_fails_itemizing_each_dead_code_issue_with_its_category_and_location_in_verbose_mode(
    run_fallow: RunFallow, fake_proc: FakeProc, fail: MakeFinding
) -> None:
    result = _run_dead_code_with_issues(run_fallow, fake_proc, verbose=True)
    assert result.findings == [
        fail(
            "fallow found 2 dead-code issues\n"
            "    unused_files: src/orphan.ts\n"
            "    unused_exports: src/lib.ts:2 unusedThing",
        )
    ]


def test_29_6_2_keeps_the_count_and_rerun_hint_failure_without_verbose(
    run_fallow: RunFallow, fake_proc: FakeProc, npm_tool_spec: NpmToolSpec, fail: MakeFinding
) -> None:
    result = _run_dead_code_with_issues(run_fallow, fake_proc, verbose=False)
    assert result.findings == [
        fail(f"fallow found 2 dead-code issues; run `bunx {npm_tool_spec('fallow')} dead-code` locally for details")
    ]


_DEAD_CODE_WITH_DEPENDENCY_AND_ENVELOPE_NOISE = json.dumps({
    "kind": "dead-code",
    "schema_version": 7,
    "version": "3.3.0",
    "total_issues": 1,
    "unused_dev_dependencies": [
        {
            "package_name": "@zyplux/cz",
            "location": "devDependencies",
            "path": "package.json",
            "line": 51,
        },
    ],
    "workspace_diagnostics": [
        {
            "path": "tests/pytools",
            "kind": "glob-matched-no-package-json",
            "pattern": "tests/*",
            "message": "Glob 'tests/*' matched 'tests/pytools' but no package.json is present.",
        },
    ],
    "entry_points": [{"path": "src/index.ts"}],
    "next_steps": [{"id": "setup", "command": "fallow schema"}],
})


def test_29_6_3_itemizes_a_dependency_by_its_real_field_name_and_ignores_envelope_metadata(
    run_fallow: RunFallow, fake_proc: FakeProc, fail: MakeFinding
) -> None:
    fake_proc.serve("fallow dead-code", returncode=1)
    fake_proc.serve_report_file("fallow dead-code", _DEAD_CODE_WITH_DEPENDENCY_AND_ENVELOPE_NOISE)
    fake_proc.serve("fallow health")
    fake_proc.serve_report_file("fallow health", _CLEAN_HEALTH)
    result = run_fallow({"package.json": _PACKAGE_JSON}, verbose=True)
    assert result.findings == [
        fail(
            "fallow found 1 dead-code issues\n    unused_dev_dependencies: package.json:51 @zyplux/cz",
        )
    ]


def test_29_7_1_invokes_fallow_at_the_pinned_version(
    run_check_with_files: RunCheckWithFiles,
    fake_proc: FakeProc,
    npm_tool_pins: dict[str, str],
    npm_tool_spec: NpmToolSpec,
) -> None:
    _serve_clean(fake_proc)
    run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    launched_specs = {argv[1] for argv, _ in fake_proc.calls}
    assert launched_specs == {f"fallow@{npm_tool_pins['fallow']}"}
    assert launched_specs == {npm_tool_spec("fallow")}


_MAX_INLINE_FINDINGS = 25


def _health_report(offender_count: int) -> dict[str, object]:
    return {
        "kind": "health",
        "schema_version": 7,
        "version": "3.3.0",
        "elapsed_ms": 9,
        "findings": [
            {
                "path": f"src/rules/offender_{i}.ts",
                "name": f"offender{i}",
                "line": i + 1,
                "cyclomatic": 25,
                "cognitive": 30,
                "crap": 160.0,
            }
            for i in range(offender_count)
        ],
        "summary": {
            "functions_analyzed": 941,
            "functions_above_threshold": offender_count,
            "average_maintainability": 92.1,
            "max_cyclomatic_threshold": 20,
            "max_cognitive_threshold": 15,
            "max_crap_threshold": 30.0,
        },
    }


def _dead_code_report(issue_count: int) -> dict[str, object]:
    return {
        "kind": "dead-code",
        "schema_version": 7,
        "version": "3.3.0",
        "total_issues": issue_count,
        "unused_exports": [
            {"path": f"src/lib_{i}.ts", "export_name": f"unused{i}", "line": i + 1} for i in range(issue_count)
        ],
    }


def _run_health_over_threshold(run_fallow: RunFallow, fake_proc: FakeProc, report: dict[str, object]) -> CheckResult:
    fake_proc.serve("fallow dead-code")
    fake_proc.serve_report_file("fallow dead-code", _CLEAN_DEAD_CODE)
    fake_proc.serve("fallow health", returncode=1)
    fake_proc.serve_report_file("fallow health", json.dumps(report))
    return run_fallow({"package.json": _PACKAGE_JSON})


def test_29_8_1_itemizes_complexity_offenders_inline_up_to_the_cap(
    run_fallow: RunFallow, fake_proc: FakeProc, repo_root: Path
) -> None:
    result = _run_health_over_threshold(run_fallow, fake_proc, _health_report(_MAX_INLINE_FINDINGS))
    (finding,) = result.findings
    assert finding.message.count("\n") == _MAX_INLINE_FINDINGS
    assert ".reports" not in finding.message
    assert not (repo_root / ".reports").exists()


def test_29_8_2_persists_the_full_health_report_and_points_to_it_once_offenders_exceed_the_cap(
    run_fallow: RunFallow, fake_proc: FakeProc, repo_root: Path, fail: MakeFinding
) -> None:
    offender_count = _MAX_INLINE_FINDINGS + 1
    report = _health_report(offender_count)
    result = _run_health_over_threshold(run_fallow, fake_proc, report)
    header = f"✗ {offender_count} above threshold · 941 analyzed · maintainability 92.1 (good) (0.01s)"
    assert result.findings == [fail(f"{header}; see .reports/fallow-health.json")]
    persisted = repo_root / ".reports" / "fallow-health.json"
    assert json.loads(persisted.read_text()) == report


def test_29_8_3_itemizes_dead_code_issues_inline_up_to_the_cap_in_verbose_mode(
    run_fallow: RunFallow, fake_proc: FakeProc, repo_root: Path
) -> None:
    report = _dead_code_report(_MAX_INLINE_FINDINGS)
    result = _run_dead_code(run_fallow, fake_proc, json.dumps(report), verbose=True)
    (finding,) = result.findings
    assert finding.message.count("\n") == _MAX_INLINE_FINDINGS
    assert ".reports" not in finding.message
    assert not (repo_root / ".reports").exists()


def test_29_8_4_persists_the_full_dead_code_report_and_points_to_it_once_issues_exceed_the_cap_in_verbose_mode(
    run_fallow: RunFallow, fake_proc: FakeProc, repo_root: Path, fail: MakeFinding
) -> None:
    issue_count = _MAX_INLINE_FINDINGS + 1
    report = _dead_code_report(issue_count)
    result = _run_dead_code(run_fallow, fake_proc, json.dumps(report), verbose=True)
    assert result.findings == [fail(f"fallow found {issue_count} dead-code issues; see .reports/fallow-dead-code.json")]
    persisted = repo_root / ".reports" / "fallow-dead-code.json"
    assert json.loads(persisted.read_text()) == report


def test_29_8_5_never_persists_a_dead_code_report_without_verbose_even_past_the_cap(
    run_fallow: RunFallow,
    fake_proc: FakeProc,
    repo_root: Path,
    npm_tool_spec: NpmToolSpec,
    fail: MakeFinding,
) -> None:
    issue_count = _MAX_INLINE_FINDINGS + 1
    report_json = json.dumps(_dead_code_report(issue_count))
    result = _run_dead_code(run_fallow, fake_proc, report_json, verbose=False)
    assert result.findings == [
        fail(
            f"fallow found {issue_count} dead-code issues;"
            f" run `bunx {npm_tool_spec('fallow')} dead-code` locally for details"
        )
    ]
    assert not (repo_root / ".reports").exists()
