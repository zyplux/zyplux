from __future__ import annotations

import re
from typing import TYPE_CHECKING

from cerberus import justfile
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from collections.abc import Iterable

    from cerberus.config import Config
    from cerberus.context import Context

ID = "justfile"
SUMMARY = "recipe names, aliases, check pipeline, wrapped tool calls, no trailing whitespace"
SCOPE = Scope.CONTENT

_SEGMENT_SPLIT = re.compile(r"&&|\|\||[|;]")
_RECIPE_LINE_PREFIXES = "@-"
_TRAILING_WS = re.compile(r"[ \t]+(?=\r?\n|\Z)")


def _trailing_ws_lines(content: str) -> list[int]:
    return [n for n, line in enumerate(content.splitlines(), start=1) if line != line.rstrip(" \t")]


def _strip_trailing_ws(content: str) -> str:
    return _TRAILING_WS.sub("", content)


def _leading_command(segment: str) -> str | None:
    tokens = segment.split()
    while tokens and "=" in tokens[0] and not tokens[0].startswith("-"):
        tokens = tokens[1:]
    if not tokens:
        return None
    return tokens[0].lstrip(_RECIPE_LINE_PREFIXES)


def _bare_tool_calls(bodies: dict[str, str], wrapped_tools: Iterable[str]) -> list[tuple[str, str]]:
    """Find recipes that invoke a managed tool directly instead of through its runner.

    A managed tool (`ruff`, `rumdl`, ...) must run via `uv run`/`bunx`, so a recipe
    line whose leading command is the tool itself relies on an ambient install and
    breaks on a fresh checkout. Wrappers like `uv run ruff` lead with `uv`, so they
    are accepted; only a denylisted tool in command position is flagged.
    """
    tools = set(wrapped_tools)
    seen: set[tuple[str, str]] = set()
    calls: list[tuple[str, str]] = []
    for recipe, body in bodies.items():
        for line in body.split("\n"):
            for segment in _SEGMENT_SPLIT.split(line):
                command = _leading_command(segment)
                if command is None or command not in tools:
                    continue
                if (recipe, command) not in seen:
                    seen.add((recipe, command))
                    calls.append((recipe, command))
    return calls


def _check_trailing_ws(content: str, repo: Repo, ctx: Context, res: CheckResult) -> None:
    ws_lines = _trailing_ws_lines(content)
    if not ws_lines:
        return
    if ctx.fix:
        ctx.write_file(repo, "justfile", _strip_trailing_ws(content))
    else:
        res.fail(f"trailing whitespace on line(s) {', '.join(map(str, ws_lines))}")


def _check_aliases(actual_aliases: dict[str, str], expected: dict[str, str], kind: str, res: CheckResult) -> None:
    for alias, target in expected.items():
        actual = actual_aliases.get(alias)
        if actual is None:
            res.fail(f"missing {kind}alias `{alias} := {target}`")
        elif actual != target:
            res.fail(f"alias `{alias}` targets `{actual}`, expected `{target}`")


def _check_recipes(recipes: Iterable[str], expected: Iterable[str], kind: str, res: CheckResult) -> None:
    present = set(recipes)
    for name in expected:
        if name not in present:
            res.fail(f"missing {kind}recipe `{name}`")


def _check_pipeline(jf: justfile.Justfile, cfg: Config, res: CheckResult) -> None:
    if "default" in jf.recipes and cfg.default_recipe_marker not in jf.bodies.get("default", ""):
        res.fail(f"`default` recipe should run `{cfg.default_recipe_marker}`")
    if "check" in jf.recipes:
        deps = jf.recipes["check"]
        if not justfile.is_subsequence(list(cfg.check_pipeline), deps):
            res.fail(f"`check` dependencies {deps} must contain {list(cfg.check_pipeline)} in order")


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    content = ctx.file(repo, "justfile")
    if content is None:
        res.fail("no justfile at repo root")
        return res

    _check_trailing_ws(content, repo, ctx, res)

    try:
        jf = justfile.parse(content)
    except justfile.JustfileError as err:
        res.error(f"could not parse justfile: {err}")
        return res

    cfg = ctx.config
    _check_aliases(jf.aliases, cfg.required_aliases, "", res)
    _check_aliases(jf.aliases, cfg.recommended_aliases, "recommended ", res)
    _check_recipes(jf.recipes, cfg.required_recipes, "required ", res)
    _check_recipes(jf.recipes, cfg.recommended_recipes, "recommended ", res)
    _check_pipeline(jf, cfg, res)

    for recipe, tool in _bare_tool_calls(jf.bodies, cfg.wrapped_tools):
        res.fail(f"recipe `{recipe}` runs `{tool}` directly; managed tools must run via `uv run`/`bunx`")

    if not res.problems:
        res.ok("justfile conforms")
    return res
