from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Finding, Status

type RunCheckWithFiles = Callable[[str, dict[str, str]], CheckResult]
type RunCiSequence = Callable[..., CheckResult]

CHECK_ID = "ci-sequence"

_PY_CI = (
    "jobs:\n"
    "  gate:\n"
    "    uses: zyplux/.github/.github/workflows/gate.yml@main\n"
    "  ci:\n    steps:\n"
    "      - run: uv sync --locked --all-groups\n"
    "      - run: uv run --no-sync vulture\n"
    "      - run: uv run --no-sync rumdl check\n"
    "      - run: uv run --no-sync ruff check\n"
    "      - run: uv run --no-sync ruff format --check\n"
    "      - run: uv run --no-sync pyrefly check\n"
    "      - run: uv run --no-sync pytest\n"
)
_TS_CI = (
    "jobs:\n  ci:\n    container: ghcr.io/zyplux/ci:1.3.14\n    steps:\n"
    "      - run: bun install --frozen-lockfile\n"
    "      - run: bun run knip\n"
    "      - run: bun run typecheck\n"
    "      - run: bun run lint\n"
    "      - run: bunx prettier --check .\n"
    "      - run: bun run test\n"
)


@pytest.fixture
def run_ci_sequence(run_check_with_files: RunCheckWithFiles) -> RunCiSequence:
    def _run(*, python: bool = False, ts: bool = False, ci: str = "") -> CheckResult:
        files: dict[str, str] = {}
        if python:
            files["pyproject.toml"] = "x"
        if ts:
            files["package.json"] = "{}"
        if ci:
            files[".github/workflows/ci.yml"] = ci
        return run_check_with_files(CHECK_ID, files)

    return _run


@pytest.fixture
def sequence_pass(finding: type[Finding], status: type[Status]) -> Finding:
    return finding(status.PASS, "ci.yml runs the canonical sequence")


def test_8_1_1_skips_repos_with_no_package_json_or_pyproject_manifest(
    run_ci_sequence: RunCiSequence, finding: type[Finding], status: type[Status]
) -> None:
    result = run_ci_sequence(ci=_PY_CI)
    assert result.findings == [finding(status.SKIP, "no package.json or pyproject.toml")]


def test_8_2_1_fails_when_no_ci_workflow_file_exists(
    run_ci_sequence: RunCiSequence, finding: type[Finding], status: type[Status]
) -> None:
    result = run_ci_sequence(python=True, ci="")
    assert result.findings == [finding(status.FAIL, "no ci.yml workflow")]


@pytest.mark.parametrize("ci", ["jobs: [unterminated", "- step\n"], ids=["invalid_yaml", "non_mapping_document"])
def test_8_2_2_errors_when_the_ci_workflow_is_not_a_valid_yaml_mapping(
    run_ci_sequence: RunCiSequence, ci: str, finding: type[Finding], status: type[Status]
) -> None:
    result = run_ci_sequence(python=True, ci=ci)
    assert result.findings == [finding(status.ERROR, "ci.yml is not valid YAML")]


def test_8_3_1_passes_a_python_ci_workflow_that_runs_every_required_step_in_order(
    run_ci_sequence: RunCiSequence, sequence_pass: Finding
) -> None:
    result = run_ci_sequence(python=True, ci=_PY_CI)
    assert result.findings == [sequence_pass]


@pytest.mark.parametrize(
    ("ci", "missing_step"),
    [
        (_PY_CI.replace("      - run: uv run --no-sync pytest\n", ""), "pytest"),
        (_PY_CI.replace("uv sync --locked --all-groups", "uv sync --all-groups"), "uv sync --locked"),
    ],
    ids=["step_missing", "step_command_wrong"],
)
def test_8_3_2_fails_when_a_required_python_step_is_missing_or_does_not_match_its_required_command(
    run_ci_sequence: RunCiSequence, ci: str, missing_step: str, finding: type[Finding], status: type[Status]
) -> None:
    result = run_ci_sequence(python=True, ci=ci)
    assert result.findings == [finding(status.FAIL, f"python ci is missing `{missing_step}`")]


def test_8_3_3_fails_when_the_required_python_steps_run_out_of_canonical_order(
    run_ci_sequence: RunCiSequence, finding: type[Finding], status: type[Status]
) -> None:
    ci = (
        "jobs:\n  ci:\n    steps:\n"
        "      - run: uv sync --locked --all-groups\n"
        "      - run: uv run --no-sync pyrefly check\n"
        "      - run: uv run --no-sync vulture\n"
        "      - run: uv run --no-sync rumdl check\n"
        "      - run: uv run --no-sync ruff check\n"
        "      - run: uv run --no-sync ruff format --check\n"
        "      - run: uv run --no-sync pytest\n"
    )
    result = run_ci_sequence(python=True, ci=ci)
    assert result.findings == [
        finding(
            status.FAIL,
            "python ci steps run out of canonical order; expected ['uv sync --locked', 'vulture', 'rumdl check', "
            "'ruff check', 'ruff format --check', 'pyrefly check', 'pytest']",
        )
    ]


def test_8_4_1_passes_a_ts_ci_workflow_that_runs_every_required_step_in_order_within_the_org_container(
    run_ci_sequence: RunCiSequence, sequence_pass: Finding
) -> None:
    result = run_ci_sequence(ts=True, ci=_TS_CI)
    assert result.findings == [sequence_pass]


def test_8_4_2_fails_when_a_required_ts_step_is_missing_or_does_not_match_its_required_command(
    run_ci_sequence: RunCiSequence, finding: type[Finding], status: type[Status]
) -> None:
    ci = _TS_CI.replace("      - run: bun run knip\n", "")
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [finding(status.FAIL, "ts ci is missing `bun run knip`")]


def test_8_4_3_fails_when_the_required_ts_steps_run_out_of_canonical_order(
    run_ci_sequence: RunCiSequence, finding: type[Finding], status: type[Status]
) -> None:
    ci = (
        "jobs:\n  ci:\n    container: ghcr.io/zyplux/ci:1.3.14\n    steps:\n"
        "      - run: bun install --frozen-lockfile\n"
        "      - run: bun run typecheck\n"
        "      - run: bun run knip\n"
        "      - run: bun run lint\n"
        "      - run: bunx prettier --check .\n"
        "      - run: bun run test\n"
    )
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [
        finding(
            status.FAIL,
            "ts ci steps run out of canonical order; expected ['bun install --frozen-lockfile', 'bun run knip', "
            "'bun run typecheck', 'bun run lint', 'prettier --check', 'bun run test']",
        )
    ]


def test_8_4_4_fails_when_the_ts_job_does_not_run_in_the_org_container(
    run_ci_sequence: RunCiSequence, finding: type[Finding], status: type[Status]
) -> None:
    ci = _TS_CI.replace("    container: ghcr.io/zyplux/ci:1.3.14\n", "")
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [
        finding(status.FAIL, "bun ci should run in the `ghcr.io/zyplux/ci` container (Node-free guarantee)")
    ]


def test_8_4_5_passes_when_the_container_is_declared_as_a_mapping_with_an_image_key(
    run_ci_sequence: RunCiSequence, sequence_pass: Finding
) -> None:
    ci = _TS_CI.replace(
        "    container: ghcr.io/zyplux/ci:1.3.14\n",
        "    container:\n      image: ghcr.io/zyplux/ci:1.3.14\n",
    )
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [sequence_pass]


def test_8_5_1_fails_when_a_required_step_appears_only_in_a_comment(
    run_ci_sequence: RunCiSequence, finding: type[Finding], status: type[Status]
) -> None:
    ci = _PY_CI.replace(
        "      - run: uv run --no-sync pytest\n",
        "      - run: |\n          # uv run --no-sync pytest\n          echo skipped\n",
    )
    result = run_ci_sequence(python=True, ci=ci)
    assert result.findings == [finding(status.FAIL, "python ci is missing `pytest`")]
