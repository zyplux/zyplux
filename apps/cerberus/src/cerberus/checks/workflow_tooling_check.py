from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import yaml

from cerberus import workflow
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "workflow-tooling"
SUMMARY = "workflows set up only the workspace toolchain (uv, bun), not extra tools"
SCOPE = Scope.CONTENT

_SETUP_ACTION = re.compile(r"^(setup-|.*-toolchain$)", re.IGNORECASE)

_INSTALL_COMMANDS = (
    re.compile(r"\bapt(?:-get)?(?:\s+-{1,2}[\w=-]+)*\s+(?:install|add)\b", re.IGNORECASE),
    re.compile(r"\bapk\s+add\b", re.IGNORECASE),
    re.compile(r"\b(?:curl|wget)\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba|da|z)?sh\b", re.IGNORECASE),
    re.compile(r"\bpip3?\s+install\b", re.IGNORECASE),
    re.compile(r"\bpipx\s+install\b", re.IGNORECASE),
    re.compile(r"\bcargo\s+install\b", re.IGNORECASE),
    re.compile(r"\bgo\s+install\b", re.IGNORECASE),
    re.compile(r"\bbrew\s+install\b", re.IGNORECASE),
    re.compile(r"\bnpm\s+(?:install|i)\b[^\n]*?\s(?:-g|--global)\b", re.IGNORECASE),
    re.compile(r"\b(?:pnpm|yarn)\b[^\n]*?\bglobal\b", re.IGNORECASE),
)


def _action_repo(uses: str) -> str:
    identity = uses.split("@", 1)[0].strip()
    _owner, slash, rest = identity.partition("/")
    return rest.split("/", 1)[0] if slash else identity


def _is_setup_action(uses: str) -> bool:
    repo = _action_repo(uses)
    return bool(_SETUP_ACTION.match(repo)) or "install-action" in repo.lower()


def _check_step(name: str, step: dict[str, Any], allowed: set[str], res: CheckResult) -> None:
    uses = step.get("uses")
    if isinstance(uses, str) and _is_setup_action(uses):
        identity = uses.split("@", 1)[0].strip()
        if identity not in allowed:
            res.fail(f"{name}: installs a tool via `{identity}`; the toolchain is uv + bun")

    script = step.get("run")
    if isinstance(script, str):
        for pattern in _INSTALL_COMMANDS:
            hit = pattern.search(workflow.strip_comment_lines(script))
            if hit is not None:
                res.fail(f"{name}: installs a tool with `{hit.group(0).strip()}`")
                break


def _scan_workflow(name: str, content: str, allowed: set[str], res: CheckResult) -> None:
    try:
        doc = yaml.safe_load(content)
    except yaml.YAMLError as err:
        res.error(f"{name}: not valid YAML ({err})")
        return
    for step in workflow.job_steps(doc):
        _check_step(name, step, allowed, res)


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    workflows = ctx.workflows(repo)
    if not workflows:
        res.skip("no workflow files to scan")
        return res

    allowed = set(ctx.config.allowed_setup_actions)
    for name, content in sorted(workflows.items()):
        _scan_workflow(name, content, allowed, res)

    if not res.problems:
        res.ok("workflows install no extra tools")
    return res
