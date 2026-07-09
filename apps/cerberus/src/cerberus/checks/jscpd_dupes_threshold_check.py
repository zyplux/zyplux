"""Copy-paste duplication cap: cerberus itself runs jscpd over the repo's
workspace-registered code and enforces the configured threshold
(`[jscpd_dupes_threshold] threshold` in cerberus.toml, default 0.1%) against every
language's duplicated-token percentage from jscpd's json report — not just
the aggregate total. Cerberus owns the whole jscpd invocation: the file
selection pattern and ignore globs come from `[jscpd_dupes_threshold] pattern` and
`ignore` in cerberus.toml, scan roots come from the repo's own workspace
manifests (bun `workspaces`, uv `[tool.uv.workspace] members`), and the
subprocess runs with its cwd outside the repo so repo-local jscpd config
(`.jscpd.json`, package.json `jscpd`) can never leak in.
"""

from __future__ import annotations

import json
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cerberus import proc
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "jscpd_dupes_threshold"
SUMMARY = "copy-paste duplication per language stays under the configured jscpd threshold"
SCOPE = Scope.CONTENT

_LANGUAGE_LABEL = {"typescript": "ts", "javascript": "js", "python": "py"}


@dataclass(frozen=True)
class _LanguageStat:
    label: str
    duplicated_tokens: int
    percentage: float


def _bun_workspace_globs(repo: Repo, ctx: Context) -> list[str]:
    package_json = ctx.file(repo, "package.json")
    if package_json is None:
        return []
    workspaces = json.loads(package_json).get("workspaces", [])
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages", [])
    return list(workspaces)


def _uv_workspace_globs(repo: Repo, ctx: Context) -> list[str]:
    pyproject = ctx.file(repo, "pyproject.toml")
    if pyproject is None:
        return []
    workspace = tomllib.loads(pyproject).get("tool", {}).get("uv", {}).get("workspace", {})
    return list(workspace.get("members", []))


def _scan_roots(repo: Repo, ctx: Context) -> list[Path]:
    repo_root = ctx.source.root.resolve()
    globs = [*_bun_workspace_globs(repo, ctx), *_uv_workspace_globs(repo, ctx)]
    members = {match for glob in globs for match in repo_root.glob(glob) if match.is_dir()}
    return sorted(members) if members else [repo_root]


def _selection_argv(ctx: Context) -> list[str]:
    return [
        "bunx",
        "jscpd",
        "--pattern",
        ctx.config.jscpd_dupes_pattern,
        "--ignore",
        ",".join(ctx.config.jscpd_dupes_ignore),
    ]


def _language_stats(report: dict[str, Any]) -> list[_LanguageStat]:
    formats: dict[str, Any] = report["statistics"]["formats"]
    totals = {fmt: stats.get("total", stats) for fmt, stats in formats.items()}
    return [
        _LanguageStat(
            label=_LANGUAGE_LABEL.get(fmt, fmt),
            duplicated_tokens=total["duplicatedTokens"],
            percentage=total["percentageTokens"],
        )
        for fmt, total in totals.items()
    ]


def _clone_lines(report: dict[str, Any], repo_root: Path) -> list[str]:
    def _span(file: dict[str, Any]) -> str:
        name = Path(file["name"])
        if name.is_absolute() and name.is_relative_to(repo_root):
            name = name.relative_to(repo_root)
        start, end = file["startLoc"], file["endLoc"]
        return f"{name} [{start['line']}:{start['column']} - {end['line']}:{end['column']}]"

    return [
        f"    {_span(clone['firstFile'])} duplicates {_span(clone['secondFile'])}" for clone in report["duplicates"]
    ]


def _load_report(report_dir: Path) -> dict[str, Any] | None:
    report_path = report_dir / "jscpd-report.json"
    try:
        parsed: dict[str, Any] = json.loads(report_path.read_text())
    except OSError, ValueError:
        return None
    return parsed


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    threshold = ctx.config.jscpd_dupes_threshold
    scan_roots = [str(root) for root in _scan_roots(repo, ctx)]
    with tempfile.TemporaryDirectory(prefix="cerberus-jscpd-") as report_dir:
        argv = [
            *_selection_argv(ctx),
            "--reporters",
            "json",
            "--silent",
            "--absolute",
            "--output",
            report_dir,
            *scan_roots,
        ]
        try:
            outcome = proc.run(argv, cwd=Path(report_dir))
        except proc.ToolNotFoundError as exc:
            res.error(str(exc))
            return res
        if outcome.returncode != 0:
            rerun_hint = " ".join([*_selection_argv(ctx), *scan_roots])
            res.fail(f"jscpd exited {outcome.returncode}; run `{rerun_hint}` locally for details")
            return res
        report = _load_report(Path(report_dir))
    if report is None:
        res.error("jscpd wrote no readable json report")
        return res
    stats = _language_stats(report)
    stats_line = "; ".join(f"{s.label}: {s.duplicated_tokens} ({s.percentage:.2f}%)" for s in stats)
    offenders = [s.label for s in stats if s.percentage > threshold]
    if offenders:
        res.fail("\n".join([stats_line, *_clone_lines(report, ctx.source.root.resolve())]))
    else:
        if stats_line:
            res.detail = stats_line
        res.ok(f"duplication is under the {threshold:g}% threshold in every language")
    return res
