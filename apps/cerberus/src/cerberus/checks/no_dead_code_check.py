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

ID = "no-dead-code"
SUMMARY = "fallow finds no unused code, circular imports, or functions above its complexity thresholds"
SCOPE = Scope.CONTENT

_SHARED_FLAGS = ["--quiet", "--fail-on-issues", "--format", "json"]


def _parse_report(outcome: subprocess.CompletedProcess[str]) -> dict[str, Any] | None:
    try:
        parsed: dict[str, Any] = json.loads(outcome.stdout)
    except ValueError:
        return None
    return parsed


def _complexity_lines(report: dict[str, Any]) -> list[str]:
    thresholds = report["summary"]
    lines = []
    for offender in report["findings"]:
        metrics = (
            f"cyclomatic {offender['cyclomatic']:g}/{thresholds['max_cyclomatic_threshold']:g}, "
            f"cognitive {offender['cognitive']:g}/{thresholds['max_cognitive_threshold']:g}, "
            f"CRAP {offender['crap']:g}/{thresholds['max_crap_threshold']:g}"
        )
        lines.append(f"    {offender['path']}:{offender['line']} {offender['name']} — {metrics}")
    return lines


def _record_dead_code(res: CheckResult, outcome: subprocess.CompletedProcess[str]) -> int | None:
    report = _parse_report(outcome)
    issue_count = report.get("total_issues") if report is not None else None
    if outcome.returncode == 0:
        return issue_count
    if issue_count is None:
        res.fail(f"fallow dead-code exited {outcome.returncode}; run `bunx fallow dead-code` locally for details")
    else:
        res.fail(f"fallow found {issue_count} dead-code issues; run `bunx fallow dead-code` locally for details")
    return issue_count


def _record_complexity(res: CheckResult, outcome: subprocess.CompletedProcess[str]) -> int | None:
    report = _parse_report(outcome)
    offenders = report.get("findings") if report is not None else None
    if outcome.returncode == 0:
        return len(offenders) if offenders is not None else 0
    if report is None or not offenders:
        res.fail(f"fallow health exited {outcome.returncode}; run `bunx fallow health` locally for details")
        return None
    header = f"fallow found {len(offenders)} functions above its complexity thresholds"
    res.fail("\n".join([header, *_complexity_lines(report)]))
    return len(offenders)


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
    dead_code_count = _record_dead_code(res, outcomes[0])
    complexity_count = _record_complexity(res, outcomes[1])
    if dead_code_count is not None and complexity_count is not None:
        res.detail = f"ts: {dead_code_count + complexity_count}"
    if not res.findings:
        res.ok("fallow found no dead code, cycles, or complexity offenders")
    return res
