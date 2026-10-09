from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from cerberus import workflow
from cerberus.model import CheckResult, Repo, Scope
from cerberus.shell_commands import get_shell_parser, list_command_args, matches_tool_command
from cerberus.stacks import can_run_command

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "ci_check_sequence"
SUMMARY = "ci.yml runs the canonical check sequence per stack"
SCOPE = Scope.CONTENT

_CI_PATHS = (".github/workflows/ci.yml", ".github/workflows/ci.yaml")


def _ci_content(repo: Repo, ctx: Context) -> str | None:
    for path in _CI_PATHS:
        content = ctx.file(repo, path)
        if content is not None:
            return content
    return None


def _parse_workflow(content: str) -> dict[str, Any] | None:
    try:
        doc = yaml.safe_load(content)
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) else None


def _matches_step(command: tuple[str, ...], step: str) -> bool:
    required = tuple(step.split())
    if required[0] not in {"uv", "pnpm"}:
        prefix = ("pnpm", "exec") if required[0] == "prettier" else ("uv", "run", "--no-sync")
        if command[: len(prefix)] != prefix:
            return False
        command = command[len(prefix) :]
    return matches_tool_command(command, required)


def _parse_step_command(script: str) -> tuple[str, ...]:
    root = get_shell_parser().parse(script.encode()).root_node
    statements = [child for child in root.named_children if child.type != "comment"]
    if root.has_error or len(statements) != 1 or statements[0].type != "command":
        return ()
    if any(child.type == "&" for child in root.children):
        return ()
    parts = statements[0].named_children
    if not parts or parts[0].type != "command_name":
        return ()
    words = [*parts[0].named_children, *parts[1:]]
    if any(word.type != "word" or word.named_children for word in words):
        return ()
    return list_command_args(statements[0])


def _verify_sequence(res: CheckResult, label: str, required: tuple[str, ...], commands: list[tuple[str, ...]]) -> None:
    missing = [step for step in required if not any(_matches_step(command, step) for command in commands)]
    for step in missing:
        res.fail(f"{label} ci is missing `{step}`")
    if missing:
        return
    index = 0
    for command in commands:
        if index < len(required) and _matches_step(command, required[index]):
            index += 1
    if index != len(required):
        res.fail(f"{label} ci steps run out of canonical order; expected {list(required)}")


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    has_ts = ctx.file(repo, "package.json") is not None
    has_python = ctx.file(repo, "pyproject.toml") is not None
    if not (has_ts or has_python):
        res.skip("no package.json or pyproject.toml")
        return res

    content = _ci_content(repo, ctx)
    if content is None:
        res.fail("no ci.yml workflow")
        return res

    doc = _parse_workflow(content)
    if doc is None:
        res.error("ci.yml is not valid YAML")
        return res

    cfg = ctx.config
    commands = [_parse_step_command(script) for script in workflow.run_commands(doc)]

    if has_ts:
        _verify_sequence(
            res,
            "ts",
            tuple(step for step in cfg.ci_required_ts if can_run_command(repo, ctx, tuple(step.split()))),
            commands,
        )
    if has_python:
        _verify_sequence(
            res,
            "python",
            tuple(step for step in cfg.ci_required_python if can_run_command(repo, ctx, tuple(step.split()))),
            commands,
        )

    if not res.problems:
        res.ok("ci.yml runs the canonical sequence")
    return res
