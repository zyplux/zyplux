from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import yaml

from cerberus import workflow
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "vitest-runner"
SUMMARY = "TypeScript tests run on vitest, never bun's built-in test runner"
SCOPE = Scope.CONTENT

_TEST_FILE = re.compile(r"\.(?:test|spec)\.[cm]?[jt]sx?$")
_BUN_TEST_IMPORT = re.compile(r"""['"]bun:test['"]""")
_BUN_TEST_RUNNER = re.compile(r"\bbun\s+(?:--\S+\s+)*test\b")


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


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    if not any(_is_manifest(path) for path in ctx.paths(repo)):
        res.skip("no package.json")
        return res

    _check_sources(repo, ctx, res)
    _check_justfile(repo, ctx, res)
    _check_workflows(repo, ctx, res)

    if not res.problems:
        res.ok("TypeScript tests run on vitest")
    return res
