from __future__ import annotations

import re
from functools import cache
from importlib import resources
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from cerberus import justfile
from cerberus.model import CheckResult, Repo, Scope
from cerberus.shell_commands import list_required_commands, list_shell_commands, matches_tool_command
from cerberus.stacks import can_run_command, has_source

if TYPE_CHECKING:
    from collections.abc import Iterable

    from cerberus.config import Config
    from cerberus.context import Context

ID = "justfile"
SUMMARY = (
    "recipe names, aliases, ordered check pipeline, local cerberus run, "
    "clean via cz clean, wrapped tool calls, no trailing whitespace"
)
SCOPE = Scope.CONTENT

_TRAILING_WS = re.compile(r"[ \t]+(?=\r?\n|\Z)")
_CZ_CLEAN_INVOCATIONS = (
    ("cz", "clean"),
    ("pnpm", "run", "cz", "clean"),
    ("pnpx", "cz", "clean"),
)


def _trailing_ws_lines(content: str) -> list[int]:
    return [n for n, line in enumerate(content.splitlines(), start=1) if line != line.rstrip(" \t")]


def _strip_trailing_ws(content: str) -> str:
    return _TRAILING_WS.sub("", content)


def _invokes_cz_clean(tokens: tuple[str, ...]) -> bool:
    """Decide whether a command segment actually runs `cz clean`.

    Only the invocation shapes the org's repos actually use count: bare
    `cz clean`, `pnpm run cz clean`, and `pnpx cz clean`. `cz`/`clean`
    have to lead the segment in one of those exact shapes — a mention
    elsewhere, or a runner carrying an unrelated command that merely happens
    to be followed by the words `cz clean` (`pnpm run echo cz clean`), does
    not count.
    """
    return any(tokens[: len(invocation)] == invocation for invocation in _CZ_CLEAN_INVOCATIONS)


def _bare_tool_calls(bodies: dict[str, str], wrapped_tools: Iterable[str]) -> list[tuple[str, str]]:
    """Find recipes that invoke a managed tool directly instead of through its runner.

    A managed tool (`ruff`, `rumdl`, ...) must run via `uv run`/`pnpx`, so a recipe
    line whose leading command is the tool itself relies on an ambient install and
    breaks on a fresh checkout. Wrappers like `uv run ruff` lead with `uv`, so they
    are accepted; only a denylisted tool in command position is flagged.
    """
    tools = set(wrapped_tools)
    seen: set[tuple[str, str]] = set()
    calls: list[tuple[str, str]] = []
    for recipe, body in bodies.items():
        for args in list_shell_commands(body):
            command = args[0]
            if command in tools and (recipe, command) not in seen:
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


def _list_recipe_calls(jf: justfile.Justfile, recipe: str) -> list[str]:
    calls = list(jf.recipes.get(recipe, []))
    for args in list_required_commands(jf.bodies.get(recipe, ""), frozenset()):
        match args:
            case ("just", name, *_):
                target = jf.aliases.get(name, name)
                if target in jf.recipes:
                    calls.append(target)
    return calls


def _calc_execution_order(jf: justfile.Justfile, recipe: str, ancestors: frozenset[str] = frozenset()) -> list[str]:
    if recipe in ancestors:
        message = f"recursive just invocation in recipe `{recipe}`"
        raise justfile.JustfileError(message)
    order = []
    for target in _list_recipe_calls(jf, recipe):
        order.extend(_calc_execution_order(jf, target, ancestors | {recipe}))
    order.append(recipe)
    return order


def _normalize_tool_args(args: tuple[str, ...]) -> tuple[str, ...]:
    if len(args) > 1 and args[0] == "pnpm" and args[1] in {"test", "knip", "typecheck"}:
        return ("pnpm", "run", *args[1:])
    return args


def _list_tool_commands(
    jf: justfile.Justfile, recipe: str, repo: Repo, ctx: Context, ancestors: frozenset[str] = frozenset()
) -> list[tuple[str, ...]]:
    if recipe in ancestors:
        message = f"recursive just invocation in recipe `{recipe}`"
        raise justfile.JustfileError(message)
    manifests = frozenset(path for path in ("package.json", "pyproject.toml") if ctx.file(repo, path) is not None)
    commands = []
    for target in jf.recipes.get(recipe, []):
        commands.extend(_list_tool_commands(jf, target, repo, ctx, ancestors | {recipe}))
    for args in list_required_commands(jf.bodies.get(recipe, ""), manifests):
        match args:
            case ("just", name, *_) if jf.aliases.get(name, name) in jf.recipes:
                commands.extend(_list_tool_commands(jf, jf.aliases.get(name, name), repo, ctx, ancestors | {recipe}))
            case ("bash" | "sh", script, *_) | (script, *_) if script.endswith(".sh"):
                commands.extend(_list_script_commands(script, repo, ctx, frozenset()))
            case _:
                commands.append(_normalize_tool_args(args))
    return commands


def _list_script_commands(script: str, repo: Repo, ctx: Context, ancestors: frozenset[str]) -> list[tuple[str, ...]]:
    path = PurePosixPath(script)
    if path.is_absolute() or ".." in path.parts or str(path) in ancestors:
        return []
    content = ctx.file(repo, str(path))
    if content is None:
        return []
    script_commands = list_required_commands(content, frozenset())
    if not script_commands or script_commands[0] != ("set", "-euo", "pipefail"):
        return []
    if any(args[0] == "set" for args in list_shell_commands(content)[1:]):
        return []
    commands = []
    for args in script_commands[1:]:
        match args:
            case ("bash" | "sh", child, *_) | (child, *_) if child.endswith(".sh"):
                commands.extend(_list_script_commands(child, repo, ctx, ancestors | {str(path)}))
            case _:
                commands.append(_normalize_tool_args(args))
    return commands


@cache
def _load_baseline() -> justfile.Justfile:
    return justfile.parse(resources.files("cerberus").joinpath("baseline.just").read_text())


def _check_tool_commands(jf: justfile.Justfile, repo: Repo, ctx: Context, res: CheckResult) -> None:
    baseline = _load_baseline()
    manifests = frozenset(path for path in ("package.json", "pyproject.toml") if ctx.file(repo, path) is not None)
    for recipe in ctx.config.check_pipeline:
        if recipe not in jf.recipes:
            continue
        actual = _list_tool_commands(jf, recipe, repo, ctx)
        required = [
            args
            for args in list_required_commands(baseline.bodies.get(recipe, ""), manifests)
            if (args[0] != "pnpm" or "package.json" in manifests)
            and (args[0] != "uv" or "pyproject.toml" in manifests)
            and can_run_command(repo, ctx, args)
        ]
        missing = [args for args in required if not any(matches_tool_command(command, args) for command in actual)]
        for args in missing:
            res.fail(f"recipe `{recipe}` must run `{' '.join(args)}` without masking its failure")
        if not missing:
            remaining = iter(actual)
            if not all(any(matches_tool_command(command, args) for command in remaining) for args in required):
                res.fail(f"recipe `{recipe}` must run its required tools in baseline order")


def _check_local_cerberus_run(jf: justfile.Justfile, repo: Repo, ctx: Context, res: CheckResult) -> None:
    if "check" not in jf.recipes:
        return
    commands = _list_tool_commands(jf, "check", repo, ctx)
    if not any(matches_tool_command(args, ("uv", "run", "cerberus")) for args in commands):
        res.fail("no recipe reachable from `check` runs cerberus; add `uv run cerberus --fix` to `check`'s pipeline")


def _check_clean_uses_cz(jf: justfile.Justfile, repo: Repo, ctx: Context, res: CheckResult) -> None:
    if "clean" not in jf.recipes:
        return
    commands = _list_tool_commands(jf, "clean", repo, ctx)
    if not any(_invokes_cz_clean(args) for args in commands):
        res.fail("`clean` recipe does not run `cz clean`; replace hardcoded find/rm with `cz clean`")


def _check_pipeline(jf: justfile.Justfile, pipeline: tuple[str, ...], cfg: Config, res: CheckResult) -> None:
    marker = tuple(cfg.default_recipe_marker.split())
    if "default" in jf.recipes and not any(
        args[: len(marker)] == marker for args in list_required_commands(jf.bodies.get("default", ""), frozenset())
    ):
        res.fail(f"`default` recipe should run `{cfg.default_recipe_marker}`")
    if "check" in jf.recipes:
        deps = _calc_execution_order(jf, "check")[:-1]
        if not justfile.is_subsequence(list(pipeline), deps):
            res.fail(f"`check` steps {deps} must contain {list(pipeline)} in order")


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    content = ctx.file(repo, "justfile")
    if content is None:
        res.fail("no justfile at repo root")
        return res

    _check_trailing_ws(content, repo, ctx, res)
    content = ctx.file(repo, "justfile") or content

    try:
        jf = justfile.parse(content)
    except justfile.JustfileError as err:
        res.error(f"could not parse justfile: {err}")
        return res

    cfg = ctx.config
    source_recipes = (
        set()
        if any(has_source(repo, ctx, language) for language in ("python", "typescript"))
        else {"knip", "typecheck", "test"}
    )
    aliases = {alias: target for alias, target in cfg.required_aliases.items() if target not in source_recipes}
    recipes = tuple(recipe for recipe in cfg.required_recipes if recipe not in source_recipes)
    pipeline = tuple(recipe for recipe in cfg.check_pipeline if recipe not in source_recipes)
    _check_aliases(jf.aliases, aliases, "", res)
    _check_aliases(jf.aliases, cfg.recommended_aliases, "recommended ", res)
    _check_recipes(jf.recipes, recipes, "required ", res)
    _check_recipes(jf.recipes, cfg.recommended_recipes, "recommended ", res)
    try:
        _check_pipeline(jf, pipeline, cfg, res)
        _check_tool_commands(jf, repo, ctx, res)
        _check_local_cerberus_run(jf, repo, ctx, res)
    except justfile.JustfileError as err:
        res.fail(str(err))
    try:
        _check_clean_uses_cz(jf, repo, ctx, res)
    except justfile.JustfileError as err:
        res.fail(str(err))

    for recipe, tool in _bare_tool_calls(jf.bodies, cfg.wrapped_tools):
        res.fail(f"recipe `{recipe}` runs `{tool}` directly; managed tools must run via `uv run`/`pnpx`")

    if not res.problems:
        res.ok("justfile conforms")
    return res
