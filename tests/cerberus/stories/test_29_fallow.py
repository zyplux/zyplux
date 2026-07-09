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

_CLEAN_DEAD_CODE = json.dumps({"total_issues": 0})
_CLEAN_HEALTH = json.dumps({
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
    "elapsed_ms": 9,
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
        "functions_analyzed": 941,
        "functions_above_threshold": 2,
        "average_maintainability": 92.1,
        "max_cyclomatic_threshold": 20,
        "max_cognitive_threshold": 15,
        "max_crap_threshold": 30.0,
    },
})


def _serve_clean(fake_proc: FakeProc) -> None:
    fake_proc.serve("fallow dead-code", stdout=_CLEAN_DEAD_CODE)
    fake_proc.serve("fallow health", stdout=_CLEAN_HEALTH)


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
    ]


def _mask_shield_dir(calls: list[tuple[list[str], Path | None]]) -> list[tuple[list[str], Path | None]]:
    masked = []
    for argv, cwd in calls:
        masked_argv = list(argv)
        config_idx = masked_argv.index("--config") + 1
        shield_dir = str(Path(masked_argv[config_idx]).parent)
        masked_argv[config_idx] = masked_argv[config_idx].replace(shield_dir, _SHIELD_DIR_PLACEHOLDER)
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
    fake_proc.serve("fallow dead-code", returncode=1, stdout=json.dumps({"total_issues": 3}))
    fake_proc.serve("fallow health", stdout=_CLEAN_HEALTH)
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
    fake_proc.serve("fallow dead-code", stdout=_CLEAN_DEAD_CODE)
    fake_proc.serve("fallow health", returncode=1, stdout=_HEALTH_OVER_THRESHOLD)
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
    fake_proc.serve("fallow dead-code", stdout=_CLEAN_DEAD_CODE)
    fake_proc.serve("fallow health", returncode=1, stdout=health_without_crap)
    result = run_check_with_files(CHECK_ID, {"package.json": _PACKAGE_JSON})
    assert result.findings == [
        fail(
            "✗ 1 above threshold · 500 analyzed · maintainability 70.0 (moderate)\n"
            "    src/rules/params.ts:144 planParameter — cyclomatic 25/20, cognitive 30/15",
        )
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
    fake_proc.serve("fallow dead-code", returncode=1, stdout=json.dumps({"total_issues": 3}))
    fake_proc.serve("fallow health", returncode=1, stdout=_HEALTH_OVER_THRESHOLD)
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


def _run_dead_code_with_issues(run_fallow: RunFallow, fake_proc: FakeProc, *, verbose: bool) -> CheckResult:
    fake_proc.serve("fallow dead-code", returncode=1, stdout=_DEAD_CODE_WITH_ISSUES)
    fake_proc.serve("fallow health", stdout=_CLEAN_HEALTH)
    return run_fallow({"package.json": _PACKAGE_JSON}, verbose=verbose)


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
