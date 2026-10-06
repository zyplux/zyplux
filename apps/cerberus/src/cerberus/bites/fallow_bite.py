"""Run pinned Fallow analyses with Cerberus-owned policy and measured coverage.

Reports use files because large pnpx stdout reports can be truncated by the
subprocess pipe chain. Oversized findings are saved under .reports/.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cerberus import proc, tool_pins, workspaces
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    import subprocess

    from cerberus.context import Context
    from cerberus.model import Repo

ID = "fallow"
SUMMARY = "fallow finds no unused code, circular imports, or functions above its complexity thresholds"
SCOPE = Scope.CONTENT

_SHARED_FLAGS = ["--quiet", "--fail-on-issues", "--format", "json"]

_MAX_INLINE_FINDINGS = 25
_REPORTS_DIR_NAME = ".reports"
_HEALTH_REPORT_FILENAME = "fallow-health.json"
_DEAD_CODE_REPORT_FILENAME = "fallow-dead-code.json"


def _load_report(report_path: Path) -> dict[str, Any] | None:
    try:
        parsed: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    return parsed


_COMPLEXITY_METRICS = (
    ("cyclomatic", "max_cyclomatic_threshold", "cyclomatic"),
    ("cognitive", "max_cognitive_threshold", "cognitive"),
    ("crap", "max_crap_threshold", "CRAP"),
)


_MAINTAINABILITY_SCALE = ((85, "good"), (65, "moderate"))


def _maintainability_rating(score: float) -> str:
    return next((word for floor, word in _MAINTAINABILITY_SCALE if score >= floor), "low")


def _health_status_line(report: dict[str, Any]) -> str | None:
    summary = report.get("summary", {})
    above = summary.get("functions_above_threshold")
    analyzed = summary.get("functions_analyzed")
    maintainability = summary.get("average_maintainability")
    parts = []
    if above is not None:
        parts.append(f"{above} above threshold")
    if analyzed is not None:
        parts.append(f"{analyzed} analyzed")
    if maintainability is not None:
        parts.append(f"maintainability {maintainability:.1f} ({_maintainability_rating(maintainability)})")
    if not parts:
        return None
    glyph = "✗" if above else "✓"
    line = f"{glyph} " + " · ".join(parts)
    elapsed_ms = report.get("elapsed_ms")
    if elapsed_ms is not None:
        line += f" ({elapsed_ms / 1000:.2f}s)"
    return line


def _complexity_lines(report: dict[str, Any]) -> list[str]:
    thresholds = report["summary"]
    lines = []
    for offender in report["findings"]:
        metrics = ", ".join(
            f"{label} {offender[metric]:g}/{thresholds[threshold]:g}"
            for metric, threshold, label in _COMPLEXITY_METRICS
            if metric in offender and threshold in thresholds
        )
        lines.append(f"    {offender['path']}:{offender['line']} {offender['name']} — {metrics}")
    return lines


# fallow's dead-code report envelope wraps the issue-category arrays (the
# ones this function itemizes) in these sibling metadata fields — see
# `CheckOutput` in fallow's own `crates/output/src/check.rs`. None of them
# hold reportable issues, but several (`workspace_diagnostics`, in
# particular) are lists of dicts with their own "path" key, so they must be
# excluded by name rather than picked up as just another category.
_DEAD_CODE_META_KEYS = frozenset({
    "kind",
    "schema_version",
    "version",
    "elapsed_ms",
    "total_issues",
    "entry_points",
    "summary",
    "baseline_deltas",
    "baseline",
    "regression",
    "_meta",
    "workspace_diagnostics",
    "next_steps",
})


def _dead_code_entry_name(entry: dict[str, Any]) -> str | None:
    parent_name = entry.get("parent_name")
    member_name = entry.get("member_name")
    if parent_name and member_name:
        return f"{parent_name}.{member_name}"
    return (
        entry.get("export_name")
        or entry.get("name")
        or entry.get("package_name")
        or member_name
        or entry.get("specifier")
    )


def _dead_code_issue_lines(report: dict[str, Any]) -> list[str]:
    lines = []
    for category, entries in report.items():
        if category in _DEAD_CODE_META_KEYS or not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or "path" not in entry:
                continue
            location = entry["path"] + (f":{entry['line']}" if "line" in entry else "")
            name = _dead_code_entry_name(entry)
            suffix = f" {name}" if name else ""
            lines.append(f"    {category}: {location}{suffix}")
    return lines


def _persist_report(ctx: Context, report: dict[str, Any], filename: str) -> Path:
    repo_root = ctx.source.root.resolve()
    reports_dir = repo_root / _REPORTS_DIR_NAME
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / filename
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path.relative_to(repo_root)


@dataclass(frozen=True)
class _Analysis:
    outcome: subprocess.CompletedProcess[str]
    report: dict[str, Any] | None


def _record_dead_code(res: CheckResult, ctx: Context, analysis: _Analysis, *, verbose: bool, runner: str) -> None:
    outcome, report = analysis.outcome, analysis.report
    if outcome.returncode == 0:
        return
    rerun_hint = f"run `{runner} {tool_pins.format_spec('fallow')} dead-code` locally for details"
    issue_count = report.get("total_issues") if report is not None else None
    if report is None or issue_count is None:
        res.fail(f"fallow dead-code exited {outcome.returncode}; {rerun_hint}")
        return
    issue_lines: list[str] = _dead_code_issue_lines(report) if verbose else []
    if not issue_lines:
        res.fail(f"fallow found {issue_count} dead-code issues; {rerun_hint}")
    elif len(issue_lines) > _MAX_INLINE_FINDINGS:
        report_path = _persist_report(ctx, report, _DEAD_CODE_REPORT_FILENAME)
        res.fail(f"fallow found {issue_count} dead-code issues; see {report_path}")
    else:
        res.fail("\n".join([f"fallow found {issue_count} dead-code issues", *issue_lines]))


def _record_complexity(res: CheckResult, ctx: Context, analysis: _Analysis, *, runner: str) -> None:
    outcome, report = analysis.outcome, analysis.report
    if outcome.returncode == 0:
        return
    offenders = report.get("findings") if report is not None else None
    if report is None or not offenders:
        res.fail(
            f"fallow health exited {outcome.returncode};"
            f" run `{runner} {tool_pins.format_spec('fallow')} health` locally for details"
        )
        return
    header = _health_status_line(report) or f"fallow found {len(offenders)} functions above its complexity thresholds"
    if len(offenders) > _MAX_INLINE_FINDINGS:
        report_path = _persist_report(ctx, report, _HEALTH_REPORT_FILENAME)
        res.fail(f"{header}; see {report_path}")
    else:
        res.fail("\n".join([header, *_complexity_lines(report)]))


def _packageless_member_dirs(repo: Repo, ctx: Context) -> list[str]:
    repo_root = ctx.source.root.resolve()
    members = workspaces.member_paths(repo_root, workspaces.ts_member_globs(repo, ctx))
    return [m.relative_to(repo_root).as_posix() for m in members if not (m / "package.json").is_file()]


def _validate_inputs(ctx: Context, res: CheckResult) -> None:
    repo_root = ctx.source.root.resolve()
    for entry in ctx.config.fallow_entry_points:
        path = (repo_root / entry).resolve()
        if not path.is_relative_to(repo_root) or not path.is_file():
            res.fail(f"fallow entry_points must name existing repository files: {entry}")
    coverage_path = (repo_root / ctx.config.fallow_coverage_report).resolve()
    if not coverage_path.is_relative_to(repo_root):
        res.fail("fallow coverage_report must be inside the repository")


def _run_analyses(ctx: Context, ignored_dirs: list[str]) -> dict[str, _Analysis]:
    analyses: dict[str, _Analysis] = {}
    coverage_path = (ctx.source.root / ctx.config.fallow_coverage_report).resolve()
    with tempfile.TemporaryDirectory(prefix="cerberus-fallow-") as shield_dir:
        config_path = Path(shield_dir) / "fallow.json"
        shield_config: dict[str, Any] = {"ignorePatterns": ignored_dirs, "duplicates": {"ignoreDefaults": False}}
        if ctx.config.fallow_entry_points:
            shield_config["entry"] = list(ctx.config.fallow_entry_points)
        config_path.write_text(json.dumps(shield_config))
        flags = [*_SHARED_FLAGS, "--root", str(ctx.source.root.resolve()), "--config", str(config_path)]
        for analysis in ("dead-code", "health"):
            report_path = Path(shield_dir) / f"{analysis}-report.json"
            coverage_flags: list[str] = []
            if analysis == "health" and coverage_path.is_file():
                coverage_flags = ["--coverage", str(coverage_path)]
            argv = [
                "pnpx",
                tool_pins.format_spec("fallow"),
                analysis,
                *flags,
                *coverage_flags,
                "--output-file",
                str(report_path),
            ]
            outcome = proc.run(argv, cwd=Path(shield_dir))
            analyses[analysis] = _Analysis(outcome, _load_report(report_path))
    return analyses


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    if ctx.file(repo, "package.json") is None:
        res.skip("no package.json")
        return res
    _validate_inputs(ctx, res)
    if res.problems:
        return res
    try:
        analyses = _run_analyses(ctx, _packageless_member_dirs(repo, ctx))
    except yaml.YAMLError as exc:
        res.error(f"pnpm-workspace.yaml is not valid YAML: {exc}")
        return res
    except proc.ToolNotFoundError as exc:
        res.error(str(exc))
        return res
    _record_dead_code(res, ctx, analyses["dead-code"], verbose=ctx.verbose, runner="pnpx")
    _record_complexity(res, ctx, analyses["health"], runner="pnpx")
    if not res.findings:
        if analyses["health"].report is not None:
            res.detail = _health_status_line(analyses["health"].report)
        res.ok("fallow found no dead code, cycles, or complexity offenders")
    return res
