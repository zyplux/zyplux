from __future__ import annotations

import re
from typing import TYPE_CHECKING

from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "vitest_coverage_floor"
SUMMARY = "vitest enforces a coverage floor of at least 90% via the root vitest.config's coverage.thresholds"
SCOPE = Scope.CONTENT

MIN_COVERAGE = 90
_THRESHOLD_KEYS = ("branches", "functions", "lines", "statements")
_ROOT_CONFIG = re.compile(r"^vitest\.config\.[cm]?[jt]s$")


def _extract_block(content: str, key: str) -> str | None:
    opening = re.search(rf"\b{key}\s*:\s*{{", content)
    if opening is None:
        return None
    start = opening.end() - 1
    depth = 0
    for index in range(start, len(content)):
        if content[index] == "{":
            depth += 1
        elif content[index] == "}":
            depth -= 1
            if depth == 0:
                return content[start : index + 1]
    return None


def _threshold_value(block: str, key: str) -> float | None:
    match = re.search(rf"\b{key}\s*:\s*(-?\d+(?:\.\d+)?)", block)
    return float(match.group(1)) if match else None


def _check_thresholds(path: str, thresholds: str, res: CheckResult) -> None:
    for key in _THRESHOLD_KEYS:
        value = _threshold_value(thresholds, key)
        if value is None:
            res.fail(f"{path} coverage.thresholds has no `{key}`; must be set to at least {MIN_COVERAGE}")
        elif value < MIN_COVERAGE:
            res.fail(f"{path} coverage.thresholds.{key} is {value}, below the required {MIN_COVERAGE}")


def _check_config(path: str, content: str, res: CheckResult) -> None:
    coverage = _extract_block(content, "coverage")
    if coverage is None:
        res.fail(f"{path} has no `coverage` block; vitest coverage must enforce a floor of at least {MIN_COVERAGE}%")
        return
    thresholds = _extract_block(coverage, "thresholds")
    if thresholds is None:
        res.fail(
            f"{path} `coverage` has no `thresholds`; must set branches/functions/lines/statements "
            f"to at least {MIN_COVERAGE}"
        )
        return
    _check_thresholds(path, thresholds, res)


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    configs = sorted(path for path in ctx.paths(repo) if _ROOT_CONFIG.match(path))
    if not configs:
        res.skip("no root vitest.config")
        return res

    for path in configs:
        content = ctx.file(repo, path)
        if content is None:
            res.error(f"could not read {path}")
            continue
        _check_config(path, content, res)

    if not res.problems:
        res.ok(f"vitest coverage gate enforces >= {MIN_COVERAGE}% (coverage.thresholds)")
    return res
