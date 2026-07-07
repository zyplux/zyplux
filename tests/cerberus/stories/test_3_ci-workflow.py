from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Finding, Status

type RunCheckWithFiles = Callable[[str, dict[str, str]], CheckResult]
type RunCiWorkflow = Callable[[str | None], CheckResult]

CHECK_ID = "ci-workflow"


@pytest.fixture
def run_ci_workflow(run_check_with_files: RunCheckWithFiles) -> RunCiWorkflow:
    def _run(workflow_content: str | None) -> CheckResult:
        files = {} if workflow_content is None else {".github/workflows/ci.yml": workflow_content}
        return run_check_with_files(CHECK_ID, files)

    return _run


def test_3_1_1_fails_when_no_workflow_file_exists(run_ci_workflow: RunCiWorkflow, finding: type[Finding], status: type[Status]) -> None:
    result = run_ci_workflow(None)
    assert result.findings == [finding(status.FAIL, "no .github/workflows/ci.yml")]


def test_3_1_2_errors_on_invalid_yaml(run_ci_workflow: RunCiWorkflow, status: type[Status]) -> None:
    result = run_ci_workflow("a: [unterminated")
    assert result.status is status.ERROR
    assert result.findings[0].message.startswith("ci.yml is not valid YAML: ")


def test_3_1_3_errors_when_the_workflow_is_not_a_mapping(run_ci_workflow: RunCiWorkflow, finding: type[Finding], status: type[Status]) -> None:
    result = run_ci_workflow("- just\n- a\n- list\n")
    assert result.findings == [finding(status.ERROR, "ci.yml did not parse to a mapping")]


def test_3_1_4_passes_when_the_workflow_lives_at_the_yaml_extension(
    run_check_with_files: RunCheckWithFiles, finding: type[Finding], status: type[Status]
) -> None:
    workflow = "on: pull_request\njobs:\n  ci:\n    name: ci\n"
    result = run_check_with_files(CHECK_ID, {".github/workflows/ci.yaml": workflow})
    assert result.findings == [finding(status.PASS, "ci workflow present and wired")]


def test_3_2_1_fails_without_a_job_named_ci(run_ci_workflow: RunCiWorkflow, finding: type[Finding], status: type[Status]) -> None:
    result = run_ci_workflow("on: [pull_request, push]\njobs:\n  build:\n    name: build\n")
    assert result.findings == [finding(status.FAIL, "no job named `ci` (the required status-check context)")]


def test_3_2_2_passes_when_a_job_id_is_named_ci(run_ci_workflow: RunCiWorkflow, finding: type[Finding], status: type[Status]) -> None:
    result = run_ci_workflow("on: [pull_request, push]\njobs:\n  ci:\n    runs-on: x\n")
    assert result.findings == [finding(status.PASS, "ci workflow present and wired")]


def test_3_2_3_passes_when_a_job_name_field_is_ci(run_ci_workflow: RunCiWorkflow, finding: type[Finding], status: type[Status]) -> None:
    result = run_ci_workflow("on: pull_request\njobs:\n  build:\n    name: ci\n")
    assert result.findings == [finding(status.PASS, "ci workflow present and wired")]


def test_3_3_1_fails_without_a_pull_request_trigger(run_ci_workflow: RunCiWorkflow, finding: type[Finding], status: type[Status]) -> None:
    result = run_ci_workflow("on: push\njobs:\n  ci:\n    name: ci\n")
    assert result.findings == [finding(status.FAIL, "ci.yml does not trigger on pull_request")]


@pytest.mark.parametrize("trigger", ["pull_request", "pull_request_target"])
def test_3_3_2_passes_with_a_pull_request_or_pull_request_target_trigger(
    run_ci_workflow: RunCiWorkflow, trigger: str, finding: type[Finding], status: type[Status]
) -> None:
    result = run_ci_workflow(f"on: {trigger}\njobs:\n  ci:\n    name: ci\n")
    assert result.findings == [finding(status.PASS, "ci workflow present and wired")]


def test_3_3_3_passes_when_the_on_key_parses_to_a_boolean(run_ci_workflow: RunCiWorkflow, finding: type[Finding], status: type[Status]) -> None:
    bare_on_key_parsed_as_pyyaml_bool = "on:\n  pull_request:\n  push:\njobs:\n  ci:\n    name: ci\n"
    result = run_ci_workflow(bare_on_key_parsed_as_pyyaml_bool)
    assert result.findings == [finding(status.PASS, "ci workflow present and wired")]
