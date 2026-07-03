from collections.abc import Callable
from pathlib import Path

import pytest
from cerberus import config, context
from cerberus.checks import workflow_tooling_check
from cerberus.model import CheckResult, Finding, Repo, Status

RunWorkflowTooling = Callable[[dict[str, str]], CheckResult]

_CLEAN_WORKFLOW = (
    "jobs:\n"
    "  ci:\n"
    "    steps:\n"
    "      - uses: actions/checkout@v6\n"
    "      - uses: astral-sh/setup-uv@v8.2.0\n"
    "      - uses: oven-sh/setup-bun@v2\n"
    "      - run: uv sync --locked\n"
    "      - run: bun install --frozen-lockfile\n"
)


@pytest.fixture
def repo() -> Repo:
    return Repo("demo")


@pytest.fixture
def ctx() -> context.Context:
    return context.local_context(config.load(), Path())


@pytest.fixture
def run_workflow_tooling(monkeypatch: pytest.MonkeyPatch, repo: Repo, ctx: context.Context) -> RunWorkflowTooling:
    def run(workflows: dict[str, str]) -> CheckResult:
        monkeypatch.setattr(ctx, "workflows", lambda *_: workflows)
        return workflow_tooling_check.run(repo, ctx)

    return run


def test_4_1_1_flags_a_github_action_that_sets_up_a_disallowed_tool(
    run_workflow_tooling: RunWorkflowTooling,
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - uses: actions/setup-node@v4\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [
        Finding(Status.FAIL, "ci.yml: installs a tool via `actions/setup-node`; the toolchain is uv + bun")
    ]


def test_4_1_2_flags_a_github_action_recognized_by_the_install_action_naming_convention(
    run_workflow_tooling: RunWorkflowTooling,
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - uses: taiki-e/install-action@just\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [
        Finding(Status.FAIL, "ci.yml: installs a tool via `taiki-e/install-action`; the toolchain is uv + bun")
    ]


def test_4_1_3_flags_a_shell_command_that_installs_a_tool(
    run_workflow_tooling: RunWorkflowTooling,
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - run: sudo apt-get install -y just\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [Finding(Status.FAIL, "ci.yml: installs a tool with `apt-get install`")]


def test_4_1_4_flags_apt_install_with_flags_before_the_subcommand(
    run_workflow_tooling: RunWorkflowTooling,
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - run: apt-get -y --no-install-recommends install jq\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [
        Finding(Status.FAIL, "ci.yml: installs a tool with `apt-get -y --no-install-recommends install`")
    ]


def test_4_1_5_flags_piping_a_downloaded_script_into_a_shell(
    run_workflow_tooling: RunWorkflowTooling,
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - run: curl -fsSL https://example.com/install.sh | sudo bash\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [
        Finding(Status.FAIL, "ci.yml: installs a tool with `curl -fsSL https://example.com/install.sh | sudo bash`")
    ]


def test_4_2_1_passes_when_workflows_only_set_up_the_workspace_toolchain(
    run_workflow_tooling: RunWorkflowTooling,
) -> None:
    result = run_workflow_tooling({"ci.yml": _CLEAN_WORKFLOW})

    assert result.findings == [Finding(Status.PASS, "workflows install no extra tools")]


def test_4_2_2_does_not_flag_npm_publish_as_a_tool_install(
    run_workflow_tooling: RunWorkflowTooling,
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - run: npm publish ./*.tgz --access public\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [Finding(Status.PASS, "workflows install no extra tools")]


def test_4_2_3_does_not_flag_a_download_that_never_reaches_a_shell(
    run_workflow_tooling: RunWorkflowTooling,
) -> None:
    wf = "jobs:\n  ci:\n    steps:\n      - run: curl -fsSL https://example.com/data.json | jq .version\n"

    result = run_workflow_tooling({"ci.yml": wf})

    assert result.findings == [Finding(Status.PASS, "workflows install no extra tools")]


def test_4_3_1_skips_repos_with_no_workflow_files_to_scan(
    run_workflow_tooling: RunWorkflowTooling,
) -> None:
    result = run_workflow_tooling({})

    assert result.findings == [Finding(Status.SKIP, "no workflow files to scan")]


def test_4_4_1_errors_when_a_workflow_file_is_not_valid_yaml(
    run_workflow_tooling: RunWorkflowTooling,
) -> None:
    result = run_workflow_tooling({"ci.yml": "a: [unterminated"})

    assert result.status is Status.ERROR
    assert result.findings[0].message.startswith("ci.yml: not valid YAML (")
