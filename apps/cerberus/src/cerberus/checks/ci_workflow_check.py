from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "ci-workflow"
SUMMARY = "ci.yml exists, exposes a `ci` check, runs on PRs"
SCOPE = Scope.CONTENT

YamlMapping = dict[str | bool, Any]
ON_KEY_AS_PYYAML_BOOL = True


def _triggers(workflow: YamlMapping) -> set[str]:
    raw = workflow.get("on", workflow.get(ON_KEY_AS_PYYAML_BOOL))
    if isinstance(raw, dict):
        return set(raw.keys())
    if isinstance(raw, list):
        return set(raw)
    if isinstance(raw, str):
        return {raw}
    return set()


def _exposes_ci_job(workflow: YamlMapping) -> bool:
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict):
        return False
    return any(job_id == "ci" or (j or {}).get("name") == "ci" for job_id, j in jobs.items())


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    content = ctx.file(repo, ".github/workflows/ci.yml") or ctx.file(repo, ".github/workflows/ci.yaml")
    if content is None:
        res.fail("no .github/workflows/ci.yml")
        return res

    try:
        workflow = yaml.safe_load(content)
    except yaml.YAMLError as err:
        res.error(f"ci.yml is not valid YAML: {err}")
        return res
    if not isinstance(workflow, dict):
        res.error("ci.yml did not parse to a mapping")
        return res

    if not _exposes_ci_job(workflow):
        res.fail("no job named `ci` (the required status-check context)")

    triggers = _triggers(workflow)
    if "pull_request" not in triggers and "pull_request_target" not in triggers:
        res.fail("ci.yml does not trigger on pull_request")

    if not res.problems:
        res.ok("ci workflow present and wired")
    return res
