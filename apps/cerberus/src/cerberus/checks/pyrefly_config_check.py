from __future__ import annotations

import tomllib
from pathlib import PurePosixPath
from typing import Any

from cerberus.context import Context
from cerberus.model import CheckResult, Repo, Scope

ID = "pyrefly-config"
SUMMARY = "production code type-checks under strict pyrefly; tests relax only `implicit-any`"
SCOPE = Scope.CONTENT

PYPROJECT = "pyproject.toml"
PATH = "pyrefly.toml"
REQUIRED_PRESET = "strict"
TEST_OVERRIDE = {"implicit-any": False}

_PRODUCTION_TOPS = ("apps", "packages")
_TESTS_TOP = "tests"

_ERROR_KINDS = frozenset(
    {
        "implicit-any",
        "implicit-any-parameter",
        "implicit-any-type-argument",
        "implicit-any-attribute",
        "implicit-any-empty-container",
        "explicit-any",
        "unannotated-return",
        "missing-override-decorator",
        "potential-bad-keyword-argument",
        "unused-ignore",
    }
)


def _config(content: str) -> dict[str, Any] | None:
    try:
        parsed = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else {}


def _has_pyproject_pyrefly(pyproject: str) -> bool:
    config = _config(pyproject) or {}
    tool = config.get("tool")
    return isinstance(tool, dict) and "pyrefly" in tool


def _python_roots(paths: list[str]) -> tuple[set[str], set[str]]:
    """The repo's production and test Python roots, by org layout convention.

    `apps/<name>/src` and `packages/<name>/src` (or `apps/<name>` without a src
    layout) are production; `tests/<name>` is tests.
    """
    production: set[str] = set()
    tests: set[str] = set()
    for path in paths:
        if not path.endswith(".py"):
            continue
        seg = path.split("/")
        if seg[0] == _TESTS_TOP:
            tests.add("/".join(seg[:2]) if len(seg) > 2 else _TESTS_TOP)
        elif seg[0] in _PRODUCTION_TOPS and len(seg) > 2:
            depth = 3 if len(seg) > 3 and seg[2] == "src" else 2
            production.add("/".join(seg[:depth]))
    return production, tests


def _governs(glob: str, root: str) -> bool:
    return PurePosixPath(f"{root}/_").full_match(glob)


def _covered(root: str, includes: list[str]) -> bool:
    target = PurePosixPath(root)
    return any(target == PurePosixPath(e) or PurePosixPath(e) in target.parents for e in includes)


def _weakens(errors: dict[str, Any]) -> bool:
    return any(value is False for value in errors.values())


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    pyproject = ctx.file(repo, PYPROJECT)
    if pyproject is None:
        res.skip("no pyproject.toml (not a Python repo)")
        return res

    production_roots, test_roots = _python_roots(ctx.paths(repo))
    if not production_roots and not test_roots:
        res.skip("no Python source")
        return res

    if _has_pyproject_pyrefly(pyproject):
        res.fail("pyrefly config lives in pyproject.toml; move it to a standalone pyrefly.toml")
        return res

    content = ctx.file(repo, PATH)
    if content is None:
        res.fail(f'no {PATH} at repo root (org requires `preset = "{REQUIRED_PRESET}"`)')
        return res

    config = _config(content)
    if config is None:
        res.error(f"could not parse {PATH}")
        return res

    preset = config.get("preset")
    if preset != REQUIRED_PRESET:
        res.fail(f'{PATH} must set `preset = "{REQUIRED_PRESET}"`; found {preset!r}')
        return res

    stray = sorted(key for key in config if key in _ERROR_KINDS)
    if stray:
        res.fail(f"{PATH} sets error kinds at the top level, not under errors: {', '.join(stray)}")
    top_errors = config.get("errors")
    if isinstance(top_errors, dict) and _weakens(top_errors):
        weakened = sorted(key for key, value in top_errors.items() if value is False)
        res.fail(f"top-level errors table weakens strict on all code: {', '.join(weakened)}")

    includes = _as_list(config.get("project-includes"))
    uncovered = sorted(r for r in production_roots | test_roots if not _covered(r, includes))
    if uncovered:
        res.fail(f"{PATH} project-includes does not cover: {', '.join(uncovered)}")

    sub_configs = _as_list(config.get("sub-config"))

    for sub in sub_configs:
        glob = sub.get("matches")
        errors = sub.get("errors") or {}
        if not glob:
            continue
        if _weakens(errors) and any(_governs(glob, r) for r in production_roots):
            res.fail(f"sub-config `{glob}` weakens strict on production code")

    for test_root in sorted(test_roots):
        override: dict[str, Any] = {}
        for sub in sub_configs:
            if (glob := sub.get("matches")) and _governs(glob, test_root):
                override.update(sub.get("errors") or {})
        allowed = TEST_OVERRIDE.items()
        extra = {key: value for key, value in override.items() if (key, value) not in allowed}
        if extra:
            res.fail(f"tests `{test_root}` may relax only `implicit-any`; also found {extra}")

    if not res.problems:
        res.ok(f"production strict, tests relax only `implicit-any` ({PATH})")
    return res
