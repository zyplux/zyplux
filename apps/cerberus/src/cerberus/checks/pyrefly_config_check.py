from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from cerberus.checks import py_tool_config
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "pyrefly-config"
SUMMARY = "all code, tests included, type-checks under strict pyrefly with no relaxations"
SCOPE = Scope.CONTENT

PATH = "pyrefly.toml"
REQUIRED_PRESET = "strict"

_PRODUCTION_TOPS = ("apps", "packages")
_TESTS_TOP = "tests"
_NAMESPACE_DEPTH = 2
_SRC_LAYOUT_DEPTH = 3

_ERROR_KINDS = frozenset({
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
})


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
            tests.add("/".join(seg[:_NAMESPACE_DEPTH]) if len(seg) > _NAMESPACE_DEPTH else _TESTS_TOP)
        elif seg[0] in _PRODUCTION_TOPS and len(seg) > _NAMESPACE_DEPTH:
            src_layout = len(seg) > _SRC_LAYOUT_DEPTH and seg[_NAMESPACE_DEPTH] == "src"
            depth = _SRC_LAYOUT_DEPTH if src_layout else _NAMESPACE_DEPTH
            production.add("/".join(seg[:depth]))
    return production, tests


def _covered(root: str, includes: list[str]) -> bool:
    target = PurePosixPath(root)
    return any(target == PurePosixPath(e) or PurePosixPath(e) in target.parents for e in includes)


def _weakens(errors: dict[str, Any]) -> bool:
    return any(value is False for value in errors.values())


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _check_top_level_errors(config: dict[str, Any], res: CheckResult) -> None:
    stray = sorted(key for key in config if key in _ERROR_KINDS)
    if stray:
        res.fail(f"{PATH} sets error kinds at the top level, not under errors: {', '.join(stray)}")
    top_errors = config.get("errors")
    if isinstance(top_errors, dict) and _weakens(top_errors):
        weakened = sorted(key for key, value in top_errors.items() if value is False)
        res.fail(f"top-level errors table weakens strict on all code: {', '.join(weakened)}")


def _check_coverage(config: dict[str, Any], production_roots: set[str], test_roots: set[str], res: CheckResult) -> None:
    includes = _as_list(config.get("project-includes"))
    uncovered = sorted(r for r in production_roots | test_roots if not _covered(r, includes))
    if uncovered:
        res.fail(f"{PATH} project-includes does not cover: {', '.join(uncovered)}")


def _check_sub_configs(config: dict[str, Any], res: CheckResult) -> None:
    for sub in _as_list(config.get("sub-config")):
        if not isinstance(sub, dict):
            res.fail(f"{PATH} sub-config entries must be tables; found {sub!r}")
            continue
        errors = sub.get("errors")
        if isinstance(errors, dict) and _weakens(errors):
            glob = sub.get("matches")
            weakened = sorted(key for key, value in errors.items() if value is False)
            res.fail(f"sub-config `{glob}` weakens strict; no relaxations allowed: {', '.join(weakened)}")


def _load_strict_config(repo: Repo, ctx: Context, res: CheckResult) -> dict[str, Any] | None:
    """The parsed pyrefly.toml once it is present, valid, and sets the strict preset.

    Records the failure and returns None when any of those preconditions fails.
    """
    content = ctx.file(repo, PATH)
    if content is None:
        res.fail(f'no {PATH} at repo root (org requires `preset = "{REQUIRED_PRESET}"`)')
        return None
    config = py_tool_config.parse_toml(content)
    if config is None:
        res.error(f"could not parse {PATH}")
        return None
    preset = config.get("preset")
    if preset != REQUIRED_PRESET:
        res.fail(f'{PATH} must set `preset = "{REQUIRED_PRESET}"`; found {preset!r}')
        return None
    return config


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    pyproject = py_tool_config.load_pyproject(repo, ctx, res)
    if pyproject is None:
        return res

    production_roots, test_roots = _python_roots(ctx.paths(repo))
    if not production_roots and not test_roots:
        res.skip("no Python source")
        return res

    if py_tool_config.fail_when_embedded(pyproject, "pyrefly", res):
        return res

    config = _load_strict_config(repo, ctx, res)
    if config is None:
        return res

    _check_top_level_errors(config, res)
    _check_coverage(config, production_roots, test_roots, res)
    _check_sub_configs(config, res)

    if not res.problems:
        res.ok(f"all code strict, no relaxations ({PATH})")
    return res
