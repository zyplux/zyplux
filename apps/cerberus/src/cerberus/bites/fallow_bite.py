"""Dead-code and complexity ban for the JS/TS workspace: cerberus runs
fallow's dead-code analysis (unused files, exports, dependencies, circular
imports) and its health analysis (functions above fallow's complexity
thresholds) over the checkout and fails on any finding. Cerberus owns the
whole fallow invocation: it writes its own config — ignoring only the
directories a bun workspace glob matches that hold no package.json, which
fallow would otherwise warn about during workspace discovery, and switching
off fallow's default duplicate ignores so test files are analyzed like any
other code — and runs the
subprocess with `--root`/`--config` from a cwd outside the repo, so
repo-local fallow config (`.fallowrc.json`, `fallow.toml`) can never leak
in. `--quiet --fail-on-issues` makes each run non-interactive with the
verdict in the exit code, and fallow itself runs at the exact version
pinned in `cerberus.tool_pins` so every run analyzes with the same tool.
Fallow analyzes only TypeScript/JavaScript, so a repo without a
`package.json` is out of scope.

Each analysis writes its report to a file via fallow's own `--output-file`
rather than being read off `outcome.stdout`: relaying a large JSON report
through the `bunx` -> fallow subprocess pipe chain has been observed to
truncate silently at a pipe-buffer-sized boundary on real-world repos
(confirmed against `fallow@3.3.0` — a multi-hundred-KB health report cuts
off at an exact multiple of 64KiB), which produces unparseable JSON and
would otherwise be indistinguishable from a genuine fallow crash. Writing
to a file sidesteps that pipe entirely, matching the same file-based
report convention `jscpd_bite` already uses for the same reason.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

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


def _load_report(report_path: Path) -> dict[str, Any] | None:
    try:
        parsed: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
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


def _record_dead_code(
    res: CheckResult,
    outcome: subprocess.CompletedProcess[str],
    report: dict[str, Any] | None,
    *,
    verbose: bool,
) -> None:
    if outcome.returncode == 0:
        return
    rerun_hint = f"run `bunx {tool_pins.format_spec('fallow')} dead-code` locally for details"
    issue_count = report.get("total_issues") if report is not None else None
    if report is None or issue_count is None:
        res.fail(f"fallow dead-code exited {outcome.returncode}; {rerun_hint}")
        return
    issue_lines: list[str] = _dead_code_issue_lines(report) if verbose else []
    if issue_lines:
        res.fail("\n".join([f"fallow found {issue_count} dead-code issues", *issue_lines]))
    else:
        res.fail(f"fallow found {issue_count} dead-code issues; {rerun_hint}")


def _record_complexity(
    res: CheckResult, outcome: subprocess.CompletedProcess[str], report: dict[str, Any] | None
) -> None:
    if outcome.returncode == 0:
        return
    offenders = report.get("findings") if report is not None else None
    if report is None or not offenders:
        res.fail(
            f"fallow health exited {outcome.returncode};"
            f" run `bunx {tool_pins.format_spec('fallow')} health` locally for details"
        )
        return
    header = _health_status_line(report) or f"fallow found {len(offenders)} functions above its complexity thresholds"
    res.fail("\n".join([header, *_complexity_lines(report)]))


def _packageless_member_dirs(repo: Repo, ctx: Context) -> list[str]:
    repo_root = ctx.source.root.resolve()
    packageless = {
        match.relative_to(repo_root).as_posix()
        for glob in workspaces.bun_member_globs(repo, ctx)
        for match in repo_root.glob(glob)
        if match.is_dir() and not (match / "package.json").is_file()
    }
    return sorted(packageless)


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    if ctx.file(repo, "package.json") is None:
        res.skip("no package.json")
        return res
    try:
        ignored_dirs = _packageless_member_dirs(repo, ctx)
    except json.JSONDecodeError as exc:
        res.error(f"package.json is not valid JSON: {exc}")
        return res
    outcomes: dict[str, subprocess.CompletedProcess[str]] = {}
    reports: dict[str, dict[str, Any] | None] = {}
    with tempfile.TemporaryDirectory(prefix="cerberus-fallow-") as shield_dir:
        config_path = Path(shield_dir) / "fallow.json"
        shield_config = {"ignorePatterns": ignored_dirs, "duplicates": {"ignoreDefaults": False}}
        config_path.write_text(json.dumps(shield_config))
        flags = [*_SHARED_FLAGS, "--root", str(ctx.source.root.resolve()), "--config", str(config_path)]
        fallow_spec = tool_pins.format_spec("fallow")
        for analysis in ("dead-code", "health"):
            report_path = Path(shield_dir) / f"{analysis}-report.json"
            argv = ["bunx", fallow_spec, analysis, *flags, "--output-file", str(report_path)]
            try:
                outcomes[analysis] = proc.run(argv, cwd=Path(shield_dir))
            except proc.ToolNotFoundError as exc:
                res.error(str(exc))
                return res
            reports[analysis] = _load_report(report_path)
    _record_dead_code(res, outcomes["dead-code"], reports["dead-code"], verbose=ctx.verbose)
    _record_complexity(res, outcomes["health"], reports["health"])
    if not res.findings:
        if reports["health"] is not None:
            res.detail = _health_status_line(reports["health"])
        res.ok("fallow found no dead code, cycles, or complexity offenders")
    return res
