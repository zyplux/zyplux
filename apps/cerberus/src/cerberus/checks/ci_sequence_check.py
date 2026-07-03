from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from cerberus import workflow
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "ci-sequence"
SUMMARY = "ci.yml runs the canonical check sequence per stack, in the org container"
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


def _container_images(doc: dict[str, Any]) -> list[str]:
    images: list[str] = []
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return images
    for job in jobs.values():
        container = job.get("container") if isinstance(job, dict) else None
        if isinstance(container, str):
            images.append(container)
        elif isinstance(container, dict) and isinstance(container.get("image"), str):
            images.append(container["image"])
    return images


def _verify_sequence(res: CheckResult, label: str, required: tuple[str, ...], commands: list[str]) -> None:
    missing = [step for step in required if not any(step in cmd for cmd in commands)]
    for step in missing:
        res.fail(f"{label} ci is missing `{step}`")
    if missing:
        return
    index = 0
    for cmd in commands:
        if index < len(required) and required[index] in cmd:
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
    commands = workflow.run_commands(doc)

    if has_ts:
        _verify_sequence(res, "ts", cfg.ci_required_ts, commands)
    if has_python:
        _verify_sequence(res, "python", cfg.ci_required_python, commands)

    if has_ts and not any(image.startswith(cfg.ci_image) for image in _container_images(doc)):
        res.fail(f"bun ci should run in the `{cfg.ci_image}` container (Node-free guarantee)")

    if not res.problems:
        res.ok("ci.yml runs the canonical sequence")
    return res
