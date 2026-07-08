"""Copy-paste duplication cap: cerberus itself runs jscpd over the checkout
and enforces the configured threshold (`[max_duplication] threshold` in
cerberus.toml, default 2%) against every language's duplicated-token
percentage from jscpd's json report — not just the aggregate total. Cerberus
owns the whole jscpd invocation: the file selection pattern and ignore globs
come from `[max_duplication] pattern` and `ignore` in cerberus.toml, so repos
need no `.jscpd.json` of their own.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cerberus import proc
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "max-duplication"
SUMMARY = "copy-paste duplication per language stays under the configured jscpd threshold"
SCOPE = Scope.CONTENT

_LANGUAGE_LABEL = {"typescript": "ts", "javascript": "js", "python": "py"}


@dataclass(frozen=True)
class _LanguageStat:
    label: str
    duplicated_tokens: int
    percentage: float


def _selection_argv(ctx: Context) -> list[str]:
    return [
        "bunx",
        "jscpd",
        "--pattern",
        ctx.config.max_duplication_pattern,
        "--ignore",
        ",".join(ctx.config.max_duplication_ignore),
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


def _clone_lines(report: dict[str, Any]) -> list[str]:
    def _span(file: dict[str, Any]) -> str:
        start, end = file["startLoc"], file["endLoc"]
        return f"{file['name']} [{start['line']}:{start['column']} - {end['line']}:{end['column']}]"

    return [f"    {_span(clone['firstFile'])} duplicates {_span(clone['secondFile'])}" for clone in report["duplicates"]]


def _load_report(report_dir: Path) -> dict[str, Any] | None:
    report_path = report_dir / "jscpd-report.json"
    try:
        parsed: dict[str, Any] = json.loads(report_path.read_text())
    except (OSError, ValueError):
        return None
    return parsed


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    threshold = ctx.config.max_duplication_threshold
    with tempfile.TemporaryDirectory(prefix="cerberus-jscpd-") as report_dir:
        argv = [*_selection_argv(ctx), "--reporters", "json", "--silent", "--output", report_dir, "."]
        try:
            outcome = proc.run(argv, cwd=ctx.source.root)
        except proc.ToolNotFoundError as exc:
            res.error(str(exc))
            return res
        if outcome.returncode != 0:
            rerun_hint = " ".join([*_selection_argv(ctx), "."])
            res.fail(f"jscpd exited {outcome.returncode}; run `{rerun_hint}` locally for details")
            return res
        report = _load_report(Path(report_dir))
    if report is None:
        res.error("jscpd wrote no readable json report")
        return res
    stats = _language_stats(report)
    if stats:
        res.detail = "; ".join(f"{s.label}: {s.duplicated_tokens} ({s.percentage:.2f}%)" for s in stats)
    offenders = [s.label for s in stats if s.percentage > threshold]
    if offenders:
        res.fail(
            "\n".join(
                [f"duplication exceeds the {threshold:g}% threshold in {', '.join(offenders)}", *_clone_lines(report)]
            )
        )
    else:
        res.ok(f"duplication is under the {threshold:g}% threshold in every language")
    return res
