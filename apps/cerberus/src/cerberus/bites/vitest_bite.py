from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import yaml

from cerberus import workflow
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "vitest"
SUMMARY = (
    "TypeScript tests run on vitest, never bun's built-in test runner, "
    "and the root vitest.config's coverage.thresholds meet the coverage floor"
)
SCOPE = Scope.CONTENT

_TEST_FILE = re.compile(r"\.(?:test|spec)\.[cm]?[jt]sx?$")
_BUN_TEST_IMPORT = re.compile(r"""['"]bun:test['"]""")
_BUN_TEST_RUNNER = re.compile(r"\bbun\s+(?:--\S+\s+)*test\b")
_THRESHOLD_KEYS = ("branches", "functions", "lines", "statements")
_ROOT_CONFIG = re.compile(r"^vitest\.config\.[cm]?[jt]s$")


def _is_vendored(path: str) -> bool:
    return "node_modules/" in path


def _is_manifest(path: str) -> bool:
    return path.rsplit("/", 1)[-1] == "package.json" and not _is_vendored(path)


def _is_test_file(path: str) -> bool:
    return _TEST_FILE.search(path) is not None and not _is_vendored(path)


def _invokes_bun_test_runner(script: str) -> bool:
    return any(_BUN_TEST_RUNNER.search(line) for line in workflow.strip_comment_lines(script).splitlines())


def _test_script(content: str) -> str:
    try:
        manifest = json.loads(content)
    except json.JSONDecodeError:
        return ""
    scripts = manifest.get("scripts") if isinstance(manifest, dict) else None
    script = scripts.get("test") if isinstance(scripts, dict) else None
    return script if isinstance(script, str) else ""


def _check_sources(repo: Repo, ctx: Context, res: CheckResult) -> None:
    for path in ctx.paths(repo):
        is_manifest = _is_manifest(path)
        is_test = _is_test_file(path)
        if not (is_manifest or is_test):
            continue
        content = ctx.file(repo, path)
        if content is None:
            continue
        if is_manifest and _BUN_TEST_RUNNER.search(_test_script(content)):
            res.fail(f"{path} `test` script runs bun's test runner; use `vitest run`")
        if is_test and _BUN_TEST_IMPORT.search(content):
            res.fail(f"{path} imports `bun:test`; import from `vitest` instead")


def _check_justfile(repo: Repo, ctx: Context, res: CheckResult) -> None:
    content = ctx.file(repo, "justfile")
    if content is not None and _invokes_bun_test_runner(content):
        res.fail("justfile runs bun's test runner; use `vitest run`")


def _check_workflows(repo: Repo, ctx: Context, res: CheckResult) -> None:
    for name, content in sorted(ctx.workflows(repo).items()):
        try:
            doc = yaml.safe_load(content)
        except yaml.YAMLError:
            continue
        if any(_invokes_bun_test_runner(command) for command in workflow.run_commands(doc)):
            res.fail(f"{name} runs bun's test runner; use `vitest run`")


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


def _check_thresholds(path: str, thresholds: str, floor: int, res: CheckResult) -> None:
    for key in _THRESHOLD_KEYS:
        value = _threshold_value(thresholds, key)
        if value is None:
            res.fail(f"{path} coverage.thresholds has no `{key}`; must be set to at least {floor}")
        elif value < floor:
            res.fail(f"{path} coverage.thresholds.{key} is {value}, below the required {floor}")


def _check_config(path: str, content: str, floor: int, res: CheckResult) -> None:
    coverage = _extract_block(content, "coverage")
    if coverage is None:
        res.fail(f"{path} has no `coverage` block; vitest coverage must enforce a floor of at least {floor}%")
        return
    thresholds = _extract_block(coverage, "thresholds")
    if thresholds is None:
        res.fail(
            f"{path} `coverage` has no `thresholds`; must set branches/functions/lines/statements to at least {floor}"
        )
        return
    _check_thresholds(path, thresholds, floor, res)


def _check_coverage_floor(repo: Repo, ctx: Context, configs: list[str], res: CheckResult) -> None:
    floor = ctx.config.vitest_min_coverage
    for path in configs:
        content = ctx.file(repo, path)
        if content is None:
            res.error(f"could not read {path}")
            continue
        _check_config(path, content, floor, res)


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    paths = ctx.paths(repo)
    has_manifest = any(_is_manifest(path) for path in paths)
    configs = sorted(path for path in paths if _ROOT_CONFIG.match(path))
    if not has_manifest and not configs:
        res.skip("no package.json or root vitest.config")
        return res

    if has_manifest:
        _check_sources(repo, ctx, res)
        _check_justfile(repo, ctx, res)
        _check_workflows(repo, ctx, res)
    _check_coverage_floor(repo, ctx, configs, res)

    if not res.problems:
        verdicts = []
        if has_manifest:
            verdicts.append("TypeScript tests run on vitest")
        if configs:
            verdicts.append(f"vitest coverage gate enforces >= {ctx.config.vitest_min_coverage}% (coverage.thresholds)")
        res.ok("; ".join(verdicts))
    return res
