"""Dead-code and complexity ban for the JS/TS workspace: cerberus runs
fallow's dead-code analysis (unused files, exports, dependencies, circular
imports) and its health analysis (functions above fallow's complexity
thresholds) over the checkout and fails on any finding. Thresholds and
ignores are the repo's business via fallow's own config; cerberus enforces
the verdict and reports the specific findings from fallow's json output.
`--quiet --fail-on-issues` makes each run non-interactive with the verdict in
the exit code. Fallow analyzes only TypeScript/JavaScript, so a repo without
a `package.json` is out of scope.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from cerberus import proc
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    import subprocess

    from cerberus.context import Context
    from cerberus.model import Repo

ID = "fallow_analyzer"
SUMMARY = "fallow finds no unused code, circular imports, or functions above its complexity thresholds"
SCOPE = Scope.CONTENT

_SHARED_FLAGS = ["--quiet", "--fail-on-issues", "--format", "json"]


def _parse_report(outcome: subprocess.CompletedProcess[str]) -> dict[str, Any] | None:
    try:
        parsed: dict[str, Any] = json.loads(outcome.stdout)
    except ValueError:
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


def _record_dead_code(res: CheckResult, outcome: subprocess.CompletedProcess[str]) -> None:
    if outcome.returncode == 0:
        return
    report = _parse_report(outcome)
    issue_count = report.get("total_issues") if report is not None else None
    if issue_count is None:
        res.fail(f"fallow dead-code exited {outcome.returncode}; run `bunx fallow dead-code` locally for details")
    else:
        res.fail(f"fallow found {issue_count} dead-code issues; run `bunx fallow dead-code` locally for details")


def _record_complexity(
    res: CheckResult, outcome: subprocess.CompletedProcess[str], report: dict[str, Any] | None
) -> None:
    if outcome.returncode == 0:
        return
    offenders = report.get("findings") if report is not None else None
    if report is None or not offenders:
        res.fail(f"fallow health exited {outcome.returncode}; run `bunx fallow health` locally for details")
        return
    header = _health_status_line(report) or f"fallow found {len(offenders)} functions above its complexity thresholds"
    res.fail("\n".join([header, *_complexity_lines(report)]))


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    if ctx.file(repo, "package.json") is None:
        res.skip("no package.json")
        return res
    outcomes = []
    for analysis in ("dead-code", "health"):
        try:
            outcomes.append(proc.run(["bunx", "fallow", analysis, *_SHARED_FLAGS], cwd=ctx.source.root))
        except proc.ToolNotFoundError as exc:
            res.error(str(exc))
            return res
    _record_dead_code(res, outcomes[0])
    health_report = _parse_report(outcomes[1])
    _record_complexity(res, outcomes[1], health_report)
    if not res.findings:
        if health_report is not None:
            res.detail = _health_status_line(health_report)
        res.ok("fallow found no dead code, cycles, or complexity offenders")
    return res
