from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml

from cerberus import workflow
from cerberus.graph.parse import extract
from cerberus.model import CheckResult, Repo, Scope
from cerberus.package_test_script import parse_test_script

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "vitest"
SUMMARY = "TypeScript tests use Vitest instead of Bun's built-in test runner"
SCOPE = Scope.CONTENT

_TEST_FILE = re.compile(r"\.(?:test|spec)\.[cm]?[jt]sx?$")
_BUN_TEST_RUNNER = re.compile(r"\bbun\s+(?:--\S+\s+)*test\b")
_ROOT_CONFIG = re.compile(r"^vitest\.config\.[cm]?[jt]s$")


def _is_vendored(path: str) -> bool:
    return "node_modules/" in path


def _is_manifest(path: str) -> bool:
    return path.rsplit("/", 1)[-1] == "package.json" and not _is_vendored(path)


def _is_test_file(path: str) -> bool:
    return _TEST_FILE.search(path) is not None and not _is_vendored(path)


def _invokes_bun_test_runner(script: str) -> bool:
    return any(_BUN_TEST_RUNNER.search(line) for line in workflow.strip_comment_lines(script).splitlines())


def _check_sources(repo: Repo, ctx: Context, res: CheckResult) -> None:
    for path in ctx.paths(repo):
        is_manifest = _is_manifest(path)
        is_test = _is_test_file(path)
        if not (is_manifest or is_test):
            continue
        content = ctx.file(repo, path)
        if content is None:
            continue
        if is_manifest and _BUN_TEST_RUNNER.search(parse_test_script(content)):
            res.fail(f"{path} `test` script runs bun's test runner; use `vitest run`")
        if is_test and "bun:test" in extract(path, content).ts_specifiers:
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

    if not res.problems:
        verdicts = []
        if has_manifest:
            verdicts.append("TypeScript tests run on vitest")

        res.ok("; ".join(verdicts))
    return res
