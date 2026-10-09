from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from cerberus import proc
from cerberus.bites import py_tool_config
from cerberus.model import CheckResult, Repo, Scope
from cerberus.stacks import has_source

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "ruff"
SUMMARY = 'ruff runs standalone in preview with `select = ["ALL"]`; relaxations stay within the sanctioned set'
SCOPE = Scope.CONTENT

PATH = "ruff.toml"

REQUIRED_SELECT = ["ALL"]

_RULE_LISTING_ARGV = ["ruff", "rule", "--all", "--output-format", "json"]


class _RuleCodes:
    """A rule's kebab-case name and its code select the same rule, so ruff — which owns that mapping — is asked for it.

    Asked only when a config spells a relaxation by name: one written in codes
    alone never reaches for the binary.
    """

    def __init__(self) -> None:
        self._by_name: dict[str, str] | None = None

    def canonical(self, selector: str) -> str:
        if self._by_name is None:
            rules = json.loads(proc.run(_RULE_LISTING_ARGV).stdout)
            self._by_name = {rule["name"]: rule["code"] for rule in rules}
        return self._by_name.get(selector, selector)


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


def _outside(selectors: list[str], sanctioned: frozenset[str], codes: _RuleCodes) -> list[str]:
    """The selectors no sanctioned relaxation covers, echoed back in the spelling the config used."""
    stray = sorted(set(selectors) - sanctioned)
    if not stray:
        return []
    allowed = {codes.canonical(rule) for rule in sanctioned}
    return [rule for rule in stray if codes.canonical(rule) not in allowed]


def _check_ignore(lint: dict[str, Any], sanctioned: frozenset[str], codes: _RuleCodes, res: CheckResult) -> None:
    stray = _outside(_as_strs(lint.get("ignore")), sanctioned, codes)
    if stray:
        res.fail(f"{PATH} ignores rules outside the sanctioned set: {', '.join(stray)}")


def _check_per_file_ignores(
    lint: dict[str, Any], sanctioned: frozenset[str], codes: _RuleCodes, res: CheckResult
) -> None:
    per_file = lint.get("per-file-ignores")
    if not isinstance(per_file, dict):
        return
    for glob, rules in per_file.items():
        stray = _outside(_as_strs(rules), sanctioned, codes)
        if stray:
            res.fail(f"per-file-ignores `{glob}` relaxes rules outside the sanctioned test set: {', '.join(stray)}")


def _load_config(repo: Repo, ctx: Context, res: CheckResult) -> dict[str, Any] | None:
    content = ctx.file(repo, PATH)
    if content is None:
        if has_source(repo, ctx, "python"):
            res.fail(f"no {PATH} at repo root (ruff config must be standalone)")
        else:
            res.skip(f"no Python source or {PATH}")
        return None
    config = py_tool_config.parse_toml(content)
    if config is None:
        res.error(f"could not parse {PATH}")
    return config


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    if py_tool_config.load_pyproject(repo, ctx, res, standalone_tool="ruff") is None:
        return res

    config = _load_config(repo, ctx, res)
    if config is None:
        return res

    _check_preview(config, res)
    lint = _lint_table(config)
    _check_select(lint, res)
    codes = _RuleCodes()
    try:
        _check_ignore(lint, ctx.config.ruff_sanctioned_ignore, codes, res)
        _check_per_file_ignores(lint, ctx.config.ruff_sanctioned_test_ignore, codes, res)
    except (proc.ToolNotFoundError, json.JSONDecodeError) as exc:
        res.error(f"could not resolve the rule names in {PATH} to their codes: {exc}")
        return res

    if not res.problems:
        res.ok(f'{PATH} is standalone, preview, select=["ALL"], relaxations within the sanctioned set')
    return res
