from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Status
    from seam_fixtures import MakeFinding, RunCheckWithWorkflows

type RunCerberusStep = Callable[[dict[str, str]], CheckResult]

CHECK_ID = "cerberus-step"


def _workflow(run_step: str) -> dict[str, str]:
    return {"ci.yml": f"jobs:\n  ci:\n    steps:\n      - run: {run_step}\n"}


@pytest.fixture
def run_cerberus_step(run_check_with_workflows: RunCheckWithWorkflows) -> RunCerberusStep:
    return partial(run_check_with_workflows, CHECK_ID)


@pytest.mark.parametrize("run_step", ["uv run cerberus", "uvx zyplux-cerberus"])
def test_7_1_1_passes_when_a_step_runs_cerberus_via_uv_run_or_the_published_uvx_package(
    run_cerberus_step: RunCerberusStep, run_step: str, ok: MakeFinding
) -> None:
    result = run_cerberus_step(_workflow(run_step))
    assert result.findings == [ok("CI runs cerberus")]


def test_7_2_1_fails_when_workflow_steps_exist_but_none_run_cerberus(
    run_cerberus_step: RunCerberusStep, fail: MakeFinding
) -> None:
    result = run_cerberus_step(_workflow("bun run test"))
    assert result.findings == [fail("no CI workflow runs cerberus (add `uvx zyplux-cerberus` to ci)")]


def test_7_2_2_fails_when_the_repo_has_no_ci_workflows_at_all(
    run_cerberus_step: RunCerberusStep, fail: MakeFinding
) -> None:
    result = run_cerberus_step({})
    assert result.findings == [fail("no CI workflow runs cerberus (add `uvx zyplux-cerberus` to ci)")]


def test_7_3_1_errors_when_a_workflow_file_is_not_valid_yaml(
    run_cerberus_step: RunCerberusStep, status: type[Status]
) -> None:
    result = run_cerberus_step({"ci.yml": "jobs: [unterminated"})
    assert result.status is status.ERROR
    assert result.findings[0].message.startswith("ci.yml is not valid YAML: ")
