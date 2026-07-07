from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any

from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "pytest-coverage"
SUMMARY = "pytest enforces a coverage floor of at least 90% via [tool.coverage.report] fail_under"
SCOPE = Scope.CONTENT

PYPROJECT = "pyproject.toml"
MIN_COVERAGE = 90


def _config(content: str) -> dict[str, Any] | None:
    try:
        parsed = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else {}


def _fail_under(config: dict[str, Any]) -> object:
    tool = config.get("tool")
    coverage = tool.get("coverage") if isinstance(tool, dict) else None
    report = coverage.get("report") if isinstance(coverage, dict) else None
    return report.get("fail_under") if isinstance(report, dict) else None


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    pyproject = ctx.file(repo, PYPROJECT)
    if pyproject is None:
        res.skip("no pyproject.toml (not a Python repo)")
        return res

    config = _config(pyproject)
    if config is None:
        res.error(f"could not parse {PYPROJECT}")
        return res

    fail_under = _fail_under(config)
    if fail_under is None:
        res.fail(f"{PYPROJECT} has no [tool.coverage.report] fail_under; pytest coverage must enforce a floor of at least {MIN_COVERAGE}%")
    elif not isinstance(fail_under, (int, float)):
        res.fail(f"{PYPROJECT} [tool.coverage.report] fail_under must be a number; found {fail_under!r}")
    elif fail_under < MIN_COVERAGE:
        res.fail(f"{PYPROJECT} [tool.coverage.report] fail_under is {fail_under}, below the required {MIN_COVERAGE}")

    if not res.problems:
        res.ok(f"pytest coverage gate enforces >= {MIN_COVERAGE}% ([tool.coverage.report] fail_under)")
    return res
