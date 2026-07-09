from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerberus.checks import py_tool_config
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "ruff-config"
SUMMARY = 'ruff runs standalone in preview with `select = ["ALL"]`; relaxations stay within the sanctioned set'
SCOPE = Scope.CONTENT

PATH = "ruff.toml"

REQUIRED_SELECT = ["ALL"]
SANCTIONED_IGNORE = frozenset({"COM812", "ISC001", "D", "DOC", "CPY001", "S404", "S603", "S606", "S607"})
SANCTIONED_TEST_IGNORE = frozenset({"ANN001", "INP001", "S101"})


def _lint_table(config: dict[str, Any]) -> dict[str, Any]:
    lint = config.get("lint")
    return lint if isinstance(lint, dict) else {}


def _as_strs(value: object) -> list[str]:
    return [str(entry) for entry in value] if isinstance(value, list) else []


def _check_preview(config: dict[str, Any], res: CheckResult) -> None:
    if config.get("preview") is not True:
        res.fail(f"{PATH} must set `preview = true` (found {config.get('preview')!r})")


def _check_select(lint: dict[str, Any], res: CheckResult) -> None:
    select = lint.get("select")
    if select != REQUIRED_SELECT:
        res.fail(f'{PATH} must set `[lint] select = ["ALL"]` (found {select!r})')


def _check_ignore(lint: dict[str, Any], res: CheckResult) -> None:
    stray = sorted(set(_as_strs(lint.get("ignore"))) - SANCTIONED_IGNORE)
    if stray:
        res.fail(f"{PATH} ignores rules outside the sanctioned set: {', '.join(stray)}")


def _check_per_file_ignores(lint: dict[str, Any], res: CheckResult) -> None:
    per_file = lint.get("per-file-ignores")
    if not isinstance(per_file, dict):
        return
    for glob, rules in per_file.items():
        stray = sorted(set(_as_strs(rules)) - SANCTIONED_TEST_IGNORE)
        if stray:
            res.fail(f"per-file-ignores `{glob}` relaxes rules outside the sanctioned test set: {', '.join(stray)}")


def _load_config(repo: Repo, ctx: Context, res: CheckResult) -> dict[str, Any] | None:
    content = ctx.file(repo, PATH)
    if content is None:
        res.fail(f"no {PATH} at repo root (ruff config must be standalone)")
        return None
    config = py_tool_config.parse_toml(content)
    if config is None:
        res.error(f"could not parse {PATH}")
    return config


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    pyproject = py_tool_config.load_pyproject(repo, ctx, res)
    if pyproject is None:
        return res

    if py_tool_config.fail_when_embedded(pyproject, "ruff", res):
        return res

    config = _load_config(repo, ctx, res)
    if config is None:
        return res

    _check_preview(config, res)
    lint = _lint_table(config)
    _check_select(lint, res)
    _check_ignore(lint, res)
    _check_per_file_ignores(lint, res)

    if not res.problems:
        res.ok(f'{PATH} is standalone, preview, select=["ALL"], relaxations within the sanctioned set')
    return res
