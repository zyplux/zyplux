"""Extract job steps and shell scripts from parsed GitHub Actions workflows."""

from __future__ import annotations

from typing import Any

from cerberus.syntax.shell_commands import strip_comment_lines


def job_steps(doc: object) -> list[dict[str, Any]]:
    """Step mappings across every job of a parsed workflow document."""
    if not isinstance(doc, dict):
        return []
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return []
    steps: list[dict[str, Any]] = []
    for job in jobs.values():
        job_step_list = job.get("steps") if isinstance(job, dict) else None
        if isinstance(job_step_list, list):
            steps.extend(step for step in job_step_list if isinstance(step, dict))
    return steps


def run_commands(doc: object) -> list[str]:
    """Executable shell text of every `run` step, with whole-line comments stripped."""
    commands: list[str] = []
    for step in job_steps(doc):
        script = step.get("run")
        if isinstance(script, str):
            commands.append(strip_comment_lines(script))
    return commands
