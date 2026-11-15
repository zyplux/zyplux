"""Check copy-paste duplication per language over workspace sources."""

from __future__ import annotations

import json
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cerberus.model import CheckResult, Scope
from cerberus.toolchain import pnpm_policy, subprocess_runner
from cerberus.workspaces import workspace_members

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "jscpd"
SUMMARY = "copy-paste duplication per language stays under the configured jscpd threshold"
SCOPE = Scope.CONTENT

_LANGUAGE_LABEL = {"typescript": "ts", "javascript": "js", "python": "py"}


@dataclass(frozen=True)
class _LanguageStat:
    label: str
    duplicated_tokens: int
    percentage: float


def _scan_roots(repo: Repo, ctx: Context) -> list[Path]:
    repo_root = ctx.source.root.resolve()
    globs = [*workspace_members.ts_member_globs(repo, ctx), *workspace_members.uv_member_globs(repo, ctx)]
    members = workspace_members.member_paths(repo_root, globs)
    return members or [repo_root]


def _selection_argv(ctx: Context) -> list[str]:
    return [
        "pnpx",
        pnpm_policy.format_spec("jscpd"),
        "--pattern",
        ctx.config.jscpd_pattern,
        "--ignore",
        ",".join(ctx.config.jscpd_ignore),
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
    threshold = ctx.config.jscpd_threshold
    try:
        scan_roots = [str(root) for root in _scan_roots(repo, ctx)]
    except yaml.YAMLError as exc:
        res.error(f"pnpm-workspace.yaml is not valid YAML: {exc}")
        return res
    except tomllib.TOMLDecodeError as exc:
        res.error(f"pyproject.toml is not valid TOML: {exc}")
        return res
    # A working directory outside the checkout isolates jscpd from repo-local configuration.
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
            outcome = subprocess_runner.run(argv, cwd=Path(report_dir))
        except subprocess_runner.ToolNotFoundError as exc:
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
        if ctx.verbose:
            res.verbose_lines = _clone_lines(report, ctx.source.root.resolve())
        res.ok(f"duplication is under the {threshold:g}% threshold in every language")
    return res
