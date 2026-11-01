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
SUMMARY = "ci.yml skips draft PRs and uses shared setup before the canonical check sequence"
SCOPE = Scope.CONTENT

_CI_PATHS = (".github/workflows/ci.yml", ".github/workflows/ci.yaml")
_DRAFT_GUARD = "github.event_name != 'pull_request' || !github.event.pull_request.draft"
_PR_EVENTS = {"opened", "synchronize", "reopened", "ready_for_review", "converted_to_draft"}


def _ci_content(repo: Repo, ctx: Context) -> str | None:
    for path in _CI_PATHS:
        content = ctx.file(repo, path)
        if content is not None:
            return content
    return None


def _parse_workflow(content: str) -> dict[str | bool, Any] | None:
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


def _is_required(step: dict[str, Any]) -> bool:
    return step.get("if", True) is True and step.get("continue-on-error", False) is False


def _has_draft_guard(job: dict[str, Any]) -> bool:
    condition = job.get("if")
    if not isinstance(condition, str):
        return False
    condition = condition.strip()
    if condition.startswith("${{") and condition.endswith("}}"):
        condition = condition[3:-2].strip()
    return condition == _DRAFT_GUARD


def _validate_draft_events(doc: dict[str | bool, Any], res: CheckResult) -> None:
    triggers = doc.get("on", doc.get(True))
    if isinstance(triggers, dict) and "pull_request_target" in triggers:
        res.fail("ci.yml must use pull_request instead of pull_request_target for draft-aware CI")
    pull_request = triggers.get("pull_request") if isinstance(triggers, dict) else None
    events = pull_request.get("types") if isinstance(pull_request, dict) else None
    if (
        not isinstance(events, list)
        or not all(isinstance(event, str) for event in events)
        or not _PR_EVENTS.issubset(events)
    ):
        res.fail(f"ci.yml pull_request.types must include {', '.join(sorted(_PR_EVENTS))}")
    concurrency = doc.get("concurrency")
    if (
        not isinstance(concurrency, dict)
        or concurrency.get("group") != "ci-${{ github.ref }}"
        or concurrency.get("cancel-in-progress") is not True
    ):
        res.fail("ci.yml must use concurrency group ci-${{ github.ref }} with cancel-in-progress: true")


def _is_shared_setup(step: dict[str, Any]) -> bool:
    uses = step.get("uses", "")
    inputs = step.get("with", {})
    identity, _, ref = uses.partition("@") if isinstance(uses, str) else ("", "", "")
    return (
        (uses == "./apps/action-setup-pm" or (identity == "zyplux/zyplux/apps/action-setup-pm" and bool(ref)))
        and _is_required(step)
        and isinstance(inputs, dict)
        and str(inputs.get("install-dependencies", "true")).lower() == "true"
    )


def _find_ci_job(doc: dict[str | bool, Any]) -> dict[str, Any] | None:
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return None
    return next(
        (job for name, job in jobs.items() if isinstance(job, dict) and (name == "ci" or job.get("name") == "ci")),
        None,
    )


def _is_root_checkout(step: dict[str, Any]) -> bool:
    uses = step.get("uses", "")
    inputs = step.get("with", {})
    return (
        isinstance(uses, str)
        and uses.startswith("actions/checkout@")
        and bool(uses.partition("@")[2])
        and _is_required(step)
        and isinstance(inputs, dict)
        and isinstance(path := inputs.get("path", ""), str)
        and path in {"", ".", "./"}
    )


def _validate_setup(steps: list[dict[str, Any]], res: CheckResult) -> int | None:
    setup_index = next((index for index, step in enumerate(steps) if _is_shared_setup(step)), None)
    if setup_index is None:
        res.fail(
            "ci.yml must use zyplux/zyplux/apps/action-setup-pm@<ref> "
            "or ./apps/action-setup-pm unconditionally before checks"
        )
        return None
    if not any(_is_root_checkout(step) for step in steps[:setup_index]):
        res.fail("ci job must check out the repository root with actions/checkout@<ref> before shared setup")
        return None
    return setup_index


def _parse_shell_command(script: str) -> tuple[str, ...]:
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


def _parse_step_commands(step: dict[str, Any]) -> list[tuple[str, ...]]:
    if not _is_required(step):
        return []
    if _is_shared_setup(step):
        return [("pnpm", "install", "--frozen-lockfile"), ("uv", "sync", "--locked")]
    script = step.get("run")
    return [_parse_shell_command(script)] if isinstance(script, str) else []


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

    job = _find_ci_job(doc)
    if job is None or not _has_draft_guard(job) or job.get("continue-on-error", False) is not False or job.get("needs"):
        res.fail(f"ci.yml must guard ci with `{_DRAFT_GUARD}`, without prerequisites or continue-on-error")
    else:
        _validate_draft_events(doc, res)
    if job is None or res.problems:
        return res
    steps = workflow.job_steps({"jobs": {"ci": job}})
    setup_index = _validate_setup(steps, res)
    if setup_index is None:
        return res

    cfg = ctx.config
    commands = [command for step in steps[setup_index:] for command in _parse_step_commands(step)]

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
