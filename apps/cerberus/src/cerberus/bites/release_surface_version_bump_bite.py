from __future__ import annotations

import json
from typing import TYPE_CHECKING

from cerberus import proc
from cerberus.model import CheckResult, Finding, Scope, Status

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "release_surface_version_bump"
SUMMARY = "a published target's version is bumped by exactly one step whenever its release surface changes"
SCOPE = Scope.GIT_HISTORY


def _parse_findings(stdout: str) -> list[Finding]:
    payload: object = json.loads(stdout)
    if not isinstance(payload, list) or not payload:
        failure = "Airlock must return a nonempty findings array"
        raise ValueError(failure)
    findings = []
    for entry in payload:
        if not isinstance(entry, dict):
            failure = "Airlock findings must be objects"
            raise TypeError(failure)
        status, message = entry.get("status"), entry.get("message")
        if not isinstance(status, str) or status.upper() not in Status.__members__:
            failure = "Airlock findings must have a valid status"
            raise ValueError(failure)
        if not isinstance(message, str) or not message.strip():
            failure = "Airlock findings must have a nonempty message"
            raise ValueError(failure)
        findings.append(Finding(Status[status.upper()], message))
    return findings


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    if ctx.file(repo, "airlock-targets.toml") is None:
        res.skip("no airlock-targets.toml — repo publishes nothing")
        return res
    try:
        outcome = proc.run(["pnpm", "exec", "airlock", "check-surface", "--json"], cwd=ctx.source.root)
    except proc.ToolNotFoundError as exc:
        res.error(str(exc))
        return res
    try:
        res.findings.extend(_parse_findings(outcome.stdout))
    except (TypeError, ValueError) as exc:
        failure = outcome.stderr.strip() or (outcome.stdout.strip() if outcome.returncode else str(exc))
        res.error(f"Airlock returned invalid findings: {failure or exc}")
        return res
    if outcome.returncode != 0 and not res.problems:
        res.error(f"Airlock exited {outcome.returncode}: {outcome.stderr.strip() or 'release validation failed'}")
    return res
