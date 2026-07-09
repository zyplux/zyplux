from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerberus.bites import py_tool_config
from cerberus.bites.py_tool_config import PYPROJECT
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "pytest"
SUMMARY = "pytest enforces a coverage floor of at least 90% via [tool.coverage.report] fail_under"
SCOPE = Scope.CONTENT


def _fail_under(config: dict[str, Any]) -> object:
    tool = config.get("tool")
    coverage = tool.get("coverage") if isinstance(tool, dict) else None
    report = coverage.get("report") if isinstance(coverage, dict) else None
    return report.get("fail_under") if isinstance(report, dict) else None


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    pyproject = py_tool_config.load_pyproject(repo, ctx, res)
    if pyproject is None:
        return res

    config = py_tool_config.parse_toml(pyproject)
    if config is None:
        res.error(f"could not parse {PYPROJECT}")
        return res

    floor = ctx.config.pytest_min_coverage
    fail_under = _fail_under(config)
    if fail_under is None:
        res.fail(
            f"{PYPROJECT} has no [tool.coverage.report] fail_under; "
            f"pytest coverage must enforce a floor of at least {floor}%"
        )
    elif not isinstance(fail_under, (int, float)):
        res.fail(f"{PYPROJECT} [tool.coverage.report] fail_under must be a number; found {fail_under!r}")
    elif fail_under < floor:
        res.fail(f"{PYPROJECT} [tool.coverage.report] fail_under is {fail_under}, below the required {floor}")

    if not res.problems:
        res.ok(f"pytest coverage gate enforces >= {floor}% ([tool.coverage.report] fail_under)")
    return res
