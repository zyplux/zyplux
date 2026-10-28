from __future__ import annotations

import fnmatch
import shlex
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from cerberus.bites import py_tool_config
from cerberus.bites.py_tool_config import PYPROJECT
from cerberus.model import CheckResult, Repo, Scope
from cerberus.source_scope import SourceKind

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "pytest"
SUMMARY = "pytest and coverage use shared source ownership and enforce a coverage floor of at least 90%"
SCOPE = Scope.CONTENT


def _fail_under(config: dict[str, Any]) -> object:
    tool = config.get("tool")
    coverage = tool.get("coverage") if isinstance(tool, dict) else None
    report = coverage.get("report") if isinstance(coverage, dict) else None
    return report.get("fail_under") if isinstance(report, dict) else None


def _words(setting: str | list[str]) -> list[str]:
    return shlex.split(setting) if isinstance(setting, str) else setting


def _check_selection(config: dict[str, Any], res: CheckResult) -> None:
    tool = config.get("tool", {})
    coverage = tool.get("coverage", {})
    run = coverage.get("run", {})
    report = coverage.get("report", {})
    ini = tool.get("pytest", {}).get("ini_options", {})
    if "cerberus.coverage_plugin" not in run.get("plugins", []):
        res.fail(
            f'{PYPROJECT} [tool.coverage.run] plugins must include "cerberus.coverage_plugin" '
            "to derive source ownership"
        )
    selectors = sorted(
        f"{section}.{key}"
        for section, settings in (("run", run), ("report", report))
        for key in ("source", "source_dirs", "source_pkgs", "include", "omit")
        if settings.get(key)
    )
    if selectors:
        res.fail(
            f"{PYPROJECT}: declare coverage ownership in [source] of cerberus.toml, not coverage {', '.join(selectors)}"
        )
    args = _words(ini.get("addopts", ""))
    if not any(
        arg == "-pcerberus" or (arg == "-p" and args[index + 1 : index + 2] == ["cerberus"])
        for index, arg in enumerate(args)
    ):
        res.fail(f'{PYPROJECT} pytest addopts must load the shared discovery policy with "-p cerberus"')
    if "--cov" not in args or any(
        arg.startswith("--cov=") or (arg == "--cov" and index + 1 < len(args) and not args[index + 1].startswith("-"))
        for index, arg in enumerate(args)
    ):
        res.fail(
            f'{PYPROJECT} pytest addopts must enable "--cov" without package selectors; '
            "Cerberus derives the measured source"
        )


def _check_discovery(config: dict[str, Any], paths: list[str], ctx: Context, res: CheckResult) -> None:
    ini = config.get("tool", {}).get("pytest", {}).get("ini_options", {})
    testpaths = _words(ini.get("testpaths", ["."]))
    filenames = _words(ini.get("python_files", ["test_*.py", "*_test.py"]))
    missing = [
        path
        for path in paths
        if path.endswith(".py")
        and ctx.config.source.classify(path).kind is not SourceKind.DEMO
        and any(fnmatch.fnmatchcase(PurePosixPath(path).name, pattern) for pattern in filenames)
        and not any(
            pattern == "."
            or any(parent.full_match(pattern) for parent in (PurePosixPath(path), *PurePosixPath(path).parents))
            for pattern in testpaths
        )
    ]
    if missing:
        res.fail(f"{PYPROJECT} pytest testpaths does not collect eligible tests: {', '.join(sorted(missing))}")


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    pyproject = py_tool_config.load_pyproject(repo, ctx, res)
    if pyproject is None:
        return res

    config = py_tool_config.parse_toml(pyproject)
    if config is None:
        res.error(f"could not parse {PYPROJECT}")
        return res

    paths = ctx.paths(repo)
    eligible = any(path.endswith(".py") and ctx.config.source.classify(path).requires_tests for path in paths)
    if not eligible and "coverage" not in config.get("tool", {}):
        res.skip("no Python source requiring tests or coverage configuration")
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

    if eligible and not res.problems:
        _check_selection(config, res)
        _check_discovery(config, paths, ctx, res)

    if not res.problems:
        res.ok(f"pytest coverage gate enforces >= {floor}% ([tool.coverage.report] fail_under)")
    return res
