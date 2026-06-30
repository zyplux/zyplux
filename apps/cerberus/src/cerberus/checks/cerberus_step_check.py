from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml

from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "cerberus-step"
SUMMARY = "a CI workflow runs cerberus to self-verify org invariants"
SCOPE = Scope.CONTENT

_CERBERUS_CALL = re.compile(r"\bcerberus\b")


def _runs_cerberus(doc: object) -> bool:
    if not isinstance(doc, dict):
        return False
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return False
    for job in jobs.values():
        steps = job.get("steps") if isinstance(job, dict) else None
        if not isinstance(steps, list):
            continue
        for step in steps:
            command = step.get("run") if isinstance(step, dict) else None
            if isinstance(command, str) and _CERBERUS_CALL.search(command):
                return True
    return False


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    for name, content in ctx.workflows(repo).items():
        try:
            doc = yaml.safe_load(content)
        except yaml.YAMLError as err:
            res.error(f"{name} is not valid YAML: {err}")
            continue
        if _runs_cerberus(doc):
            res.ok("CI runs cerberus")
            return res
    if not res.problems:
        res.fail("no CI workflow runs cerberus (add `uvx zyplux-cerberus` to ci)")
    return res
