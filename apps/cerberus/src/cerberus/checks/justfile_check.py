from __future__ import annotations

import functools
import re
from importlib import resources
from typing import TYPE_CHECKING

from cerberus import justfile
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from collections.abc import Iterable

    from cerberus.config import Config
    from cerberus.context import Context

ID = "justfile"
SUMMARY = (
    "canonical baseline block, recipe names, aliases, check pipeline, "
    "local cerberus run, wrapped tool calls, no trailing whitespace"
)
SCOPE = Scope.CONTENT

BASELINE_MARKER = "# BASELINE"
CUSTOM_MARKER = "# CUSTOM"
_MISSING_MARKERS = (
    f"baseline markers missing: line 1 must be `{BASELINE_MARKER}`, followed by the canonical baseline block "
    f"(packaged with cerberus as `baseline.just`; see zyplux/justfile), then a `{CUSTOM_MARKER}` line — "
    f"everything after `{CUSTOM_MARKER}` stays repo-specific"
)

_SEGMENT_SPLIT = re.compile(r"&&|\|\||[|;]")
_RECIPE_LINE_PREFIXES = "@-"
_TRAILING_WS = re.compile(r"[ \t]+(?=\r?\n|\Z)")
_CERBERUS_RUNNERS = frozenset({"uv", "uvx"})


def _trailing_ws_lines(content: str) -> list[int]:
    return [n for n, line in enumerate(content.splitlines(), start=1) if line != line.rstrip(" \t")]


def _strip_trailing_ws(content: str) -> str:
    return _TRAILING_WS.sub("", content)


def _command_tokens(segment: str) -> list[str]:
    tokens = segment.split()
    while tokens and "=" in tokens[0] and not tokens[0].startswith("-"):
        tokens = tokens[1:]
    if tokens:
        tokens[0] = tokens[0].lstrip(_RECIPE_LINE_PREFIXES)
    return tokens


def _leading_command(segment: str) -> str | None:
    tokens = _command_tokens(segment)
    return tokens[0] if tokens else None


def _invokes_cerberus(segment: str) -> bool:
    """Decide whether a command segment actually runs cerberus.

    `cerberus` in command position counts, as does a runner (`uv`, `uvx`)
    carrying a `cerberus` token (`uv run --active cerberus`,
    `uvx --from zyplux-cerberus cerberus`). A mention in a shell comment or as
    an argument to an unrelated command does not.
    """
    tokens = _command_tokens(segment)
    if not tokens:
        return False
    return tokens[0] == "cerberus" or (tokens[0] in _CERBERUS_RUNNERS and "cerberus" in tokens[1:])


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


@functools.cache
def _canonical_region_lines() -> tuple[str, ...]:
    baseline = resources.files("cerberus").joinpath("baseline.just").read_text()
    return (BASELINE_MARKER, *baseline.splitlines(), "", CUSTOM_MARKER)


def _first_drift(expected_region: tuple[str, ...], actual_region: list[str]) -> tuple[int, str, str] | None:
    lines = enumerate(zip(expected_region, actual_region, strict=False), start=1)
    return next(((n, expected, actual) for n, (expected, actual) in lines if expected != actual), None)


def _rewrite_baseline_region(
    content: str, custom_marker_index: int, repo: Repo, ctx: Context, res: CheckResult
) -> None:
    custom_tail = content.split("\n")[custom_marker_index + 1 :]
    fixed = "\n".join([*_canonical_region_lines(), *custom_tail])
    try:
        justfile.parse(fixed)
    except justfile.JustfileError as err:
        res.fail(
            f"baseline region not rewritten: the fixed justfile does not parse ({err}); "
            f"resolve the conflict in the `{CUSTOM_MARKER}` section first"
        )
        return
    ctx.write_file(repo, "justfile", fixed)


def _check_baseline(content: str, repo: Repo, ctx: Context, res: CheckResult) -> None:
    lines = content.split("\n")
    custom_marker_index = next((index for index, line in enumerate(lines) if line.rstrip(" \t") == CUSTOM_MARKER), None)
    if lines[0].rstrip(" \t") != BASELINE_MARKER or custom_marker_index is None:
        res.fail(_MISSING_MARKERS)
        return
    expected_region = _canonical_region_lines()
    drift = _first_drift(expected_region, lines[: custom_marker_index + 1])
    if drift is None:
        return
    if ctx.fix:
        _rewrite_baseline_region(content, custom_marker_index, repo, ctx, res)
        return
    line_number, expected, actual = drift
    res.fail(f"baseline drift at line {line_number}: expected `{expected}`, actual `{actual}`")


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


def _calc_reachable_recipes(jf: justfile.Justfile, root: str) -> set[str]:
    reachable: set[str] = set()
    frontier = [root]
    while frontier:
        recipe = frontier.pop()
        if recipe in reachable:
            continue
        reachable.add(recipe)
        frontier.extend(jf.recipes.get(recipe, []))
    return reachable


def _check_local_cerberus_run(jf: justfile.Justfile, res: CheckResult) -> None:
    if "check" not in jf.recipes:
        return
    segments = (
        segment
        for recipe in _calc_reachable_recipes(jf, "check")
        for line in jf.bodies.get(recipe, "").split("\n")
        for segment in _SEGMENT_SPLIT.split(line)
    )
    if not any(_invokes_cerberus(segment) for segment in segments):
        res.fail("no recipe reachable from `check` runs cerberus; add `uv run cerberus --fix` to `lint`")


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

    _check_baseline(content, repo, ctx, res)
    content = ctx.file(repo, "justfile") or content

    _check_trailing_ws(content, repo, ctx, res)
    content = ctx.file(repo, "justfile") or content

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
    _check_local_cerberus_run(jf, res)

    for recipe, tool in _bare_tool_calls(jf.bodies, cfg.wrapped_tools):
        res.fail(f"recipe `{recipe}` runs `{tool}` directly; managed tools must run via `uv run`/`bunx`")

    if not res.problems:
        res.ok("justfile conforms")
    return res
