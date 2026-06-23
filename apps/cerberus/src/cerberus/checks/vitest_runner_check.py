from __future__ import annotations

import json
import re

from cerberus.context import Context
from cerberus.model import CheckResult, Repo, Scope

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


def _test_script(content: str) -> str:
    try:
        manifest = json.loads(content)
    except json.JSONDecodeError:
        return ""
    scripts = manifest.get("scripts") if isinstance(manifest, dict) else None
    script = scripts.get("test") if isinstance(scripts, dict) else None
    return script if isinstance(script, str) else ""


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    paths = ctx.paths(repo)
    manifests = [path for path in paths if _is_manifest(path)]
    if not manifests:
        res.skip("no package.json")
        return res

    for path in manifests:
        content = ctx.file(repo, path)
        if content is not None and _BUN_TEST_RUNNER.search(_test_script(content)):
            res.fail(f"{path} `test` script runs bun's test runner; use `vitest run`")

    for path in paths:
        if not _is_test_file(path):
            continue
        content = ctx.file(repo, path)
        if content is not None and _BUN_TEST_IMPORT.search(content):
            res.fail(f"{path} imports `bun:test`; import from `vitest` instead")

    if not res.problems:
        res.ok("TypeScript tests run on vitest")
    return res
