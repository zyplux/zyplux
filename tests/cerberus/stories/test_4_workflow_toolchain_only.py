from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Status
    from seam_fixtures import MakeFinding, RunCheckWithWorkflows

type RunWorkflowTooling = Callable[[dict[str, str]], CheckResult]

CHECK_ID = "workflow_toolchain_only"

_CLEAN_WORKFLOW = "jobs:\n  ci:\n    steps:\n      - uses: actions/checkout@v7\n      - uses: ./setup-pm\n"


@pytest.fixture
def run_workflow_tooling(run_check_with_workflows: RunCheckWithWorkflows) -> RunWorkflowTooling:
    return partial(run_check_with_workflows, CHECK_ID)


def test_4_1_1_flags_a_github_action_that_sets_up_a_disallowed_tool(
    run_workflow_tooling: RunWorkflowTooling, fail: MakeFinding
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - uses: actions/setup-python@v5\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [
        fail(
            "ci.yml: unsupported toolchain setup `actions/setup-python@v5`; allowed: ./setup-pm, zyplux/zyplux/setup-pm"
        )
    ]


@pytest.mark.parametrize(
    "identity",
    ["taiki-e/install-action", "someorg/action-setup", "someorg/setup", "someorg/monorepo/setup-tool"],
    ids=["install-action", "action-setup", "setup", "nested-setup"],
)
def test_4_1_2_flags_a_github_action_recognized_by_the_install_action_naming_convention(
    run_workflow_tooling: RunWorkflowTooling, identity: str, fail: MakeFinding
) -> None:
    wf = f"jobs:\n  ci:\n    steps:\n      - uses: {identity}@v1\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [
        fail(f"ci.yml: unsupported toolchain setup `{identity}@v1`; allowed: ./setup-pm, zyplux/zyplux/setup-pm")
    ]


@pytest.mark.parametrize(
    "action",
    ["pnpm/action-setup@v6", "pnpm/setup@v3", "astral-sh/setup-uv@v9.0.0", "actions/setup-node@v7"],
)
def test_4_1_6_requires_the_shared_package_manager_setup_action(
    run_workflow_tooling: RunWorkflowTooling, action: str, fail: MakeFinding
) -> None:
    wf = f"jobs:\n  ci:\n    steps:\n      - uses: {action}\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [
        fail(f"ci.yml: unsupported toolchain setup `{action}`; allowed: ./setup-pm, zyplux/zyplux/setup-pm")
    ]


def test_4_1_3_flags_a_shell_command_that_installs_a_tool(
    run_workflow_tooling: RunWorkflowTooling, fail: MakeFinding
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - run: sudo apt-get install -y just\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [fail("ci.yml: installs a tool with `apt-get install`")]


def test_4_1_4_flags_apt_install_with_flags_before_the_subcommand(
    run_workflow_tooling: RunWorkflowTooling, fail: MakeFinding
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - run: apt-get -y --no-install-recommends install jq\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [fail("ci.yml: installs a tool with `apt-get -y --no-install-recommends install`")]


def test_4_1_5_flags_piping_a_downloaded_script_into_a_shell(
    run_workflow_tooling: RunWorkflowTooling, fail: MakeFinding
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - run: curl -fsSL https://example.com/install.sh | sudo bash\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [
        fail("ci.yml: installs a tool with `curl -fsSL https://example.com/install.sh | sudo bash`")
    ]


def test_4_2_1_passes_when_workflows_only_set_up_the_workspace_toolchain(
    run_workflow_tooling: RunWorkflowTooling, ok: MakeFinding
) -> None:
    result = run_workflow_tooling({"ci.yml": _CLEAN_WORKFLOW})

    assert result.findings == [ok("workflows install no extra tools")]


@pytest.mark.parametrize("action", ["./setup-pm", "zyplux/zyplux/setup-pm@main"])
def test_4_2_4_accepts_the_shared_package_manager_setup(
    run_workflow_tooling: RunWorkflowTooling, ok: MakeFinding, action: str
) -> None:
    result = run_workflow_tooling({"ci.yml": f"jobs:\n  ci:\n    steps:\n      - uses: {action}\n"})
    assert result.findings == [ok("workflows install no extra tools")]


def test_4_2_2_does_not_flag_npm_publish_as_a_tool_install(
    run_workflow_tooling: RunWorkflowTooling, ok: MakeFinding
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - run: npm publish ./*.tgz --access public\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [ok("workflows install no extra tools")]


def test_4_2_3_does_not_flag_a_download_that_never_reaches_a_shell(
    run_workflow_tooling: RunWorkflowTooling, ok: MakeFinding
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - run: curl -fsSL https://example.com/data.json | jq .version\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [ok("workflows install no extra tools")]


def test_4_3_1_skips_repos_with_no_workflow_files_to_scan(
    run_workflow_tooling: RunWorkflowTooling, skip: MakeFinding
) -> None:
    result = run_workflow_tooling({})

    assert result.findings == [skip("no workflow files to scan")]


def test_4_4_1_errors_when_a_workflow_file_is_not_valid_yaml(
    run_workflow_tooling: RunWorkflowTooling, status: type[Status]
) -> None:
    result = run_workflow_tooling({"ci.yml": "a: [unterminated"})

    assert result.status is status.ERROR
    assert result.findings[0].message.startswith("ci.yml: not valid YAML (")
