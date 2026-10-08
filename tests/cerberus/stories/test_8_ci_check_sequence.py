from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Finding
    from seam_fixtures import MakeFinding, RunCheckWithFiles

type RunCiSequence = Callable[..., CheckResult]

CHECK_ID = "ci_check_sequence"

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
    "jobs:\n  ci:\n    steps:\n"
    "      - run: pnpm install --frozen-lockfile\n"
    "      - run: pnpm run knip\n"
    "      - run: pnpm run typecheck\n"
    "      - run: pnpm run lint\n"
    "      - run: pnpx prettier --check .\n"
    "      - run: pnpm run test\n"
)


@pytest.fixture
def run_ci_sequence(run_check_with_files: RunCheckWithFiles) -> RunCiSequence:
    def _run(*, python: bool = False, ts: bool = False, ci: str = "") -> CheckResult:
        files: dict[str, str] = {}
        if python:
            files["pyproject.toml"] = "x"
            files["app.py"] = "print(1)"
        if ts:
            files["package.json"] = "{}"
            files["app.ts"] = "console.log(1);"
        if ci:
            files[".github/workflows/ci.yml"] = ci
        return run_check_with_files(CHECK_ID, files)

    return _run


@pytest.fixture
def sequence_pass(ok: MakeFinding) -> Finding:
    return ok("ci.yml runs the canonical sequence")


def test_8_1_1_skips_repos_with_no_package_json_or_pyproject_manifest(
    run_ci_sequence: RunCiSequence, skip: MakeFinding
) -> None:
    result = run_ci_sequence(ci=_PY_CI)
    assert result.findings == [skip("no package.json or pyproject.toml")]


def test_8_2_1_fails_when_no_ci_workflow_file_exists(run_ci_sequence: RunCiSequence, fail: MakeFinding) -> None:
    result = run_ci_sequence(python=True, ci="")
    assert result.findings == [fail("no ci.yml workflow")]


@pytest.mark.parametrize("ci", ["jobs: [unterminated", "- step\n"], ids=["invalid_yaml", "non_mapping_document"])
def test_8_2_2_errors_when_the_ci_workflow_is_not_a_valid_yaml_mapping(
    run_ci_sequence: RunCiSequence, ci: str, error: MakeFinding
) -> None:
    result = run_ci_sequence(python=True, ci=ci)
    assert result.findings == [error("ci.yml is not valid YAML")]


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
    run_ci_sequence: RunCiSequence, ci: str, missing_step: str, fail: MakeFinding
) -> None:
    result = run_ci_sequence(python=True, ci=ci)
    assert result.findings == [fail(f"python ci is missing `{missing_step}`")]


def test_8_3_3_fails_when_the_required_python_steps_run_out_of_canonical_order(
    run_ci_sequence: RunCiSequence, fail: MakeFinding
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
        fail(
            "python ci steps run out of canonical order; expected ['uv sync --locked', 'vulture', 'rumdl check', "
            "'ruff check', 'ruff format --check', 'pyrefly check', 'pytest']",
        )
    ]


def test_8_4_1_passes_a_ts_ci_workflow_that_runs_every_required_step_in_order(
    run_ci_sequence: RunCiSequence, sequence_pass: Finding
) -> None:
    result = run_ci_sequence(ts=True, ci=_TS_CI)
    assert result.findings == [sequence_pass]


def test_8_4_2_fails_when_a_required_ts_step_is_missing_or_does_not_match_its_required_command(
    run_ci_sequence: RunCiSequence, fail: MakeFinding
) -> None:
    ci = _TS_CI.replace("      - run: pnpm run knip\n", "")
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [fail("ts ci is missing `pnpm run knip`")]


def test_8_4_3_fails_when_the_required_ts_steps_run_out_of_canonical_order(
    run_ci_sequence: RunCiSequence, fail: MakeFinding
) -> None:
    ci = (
        "jobs:\n  ci:\n    steps:\n"
        "      - run: pnpm install --frozen-lockfile\n"
        "      - run: pnpm run typecheck\n"
        "      - run: pnpm run knip\n"
        "      - run: pnpm run lint\n"
        "      - run: pnpx prettier --check .\n"
        "      - run: pnpm run test\n"
    )
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [
        fail(
            "ts ci steps run out of canonical order; expected ['pnpm install --frozen-lockfile', 'pnpm run knip', "
            "'pnpm run typecheck', 'pnpm run lint', 'prettier --check', 'pnpm run test']",
        )
    ]


def test_8_5_1_fails_when_a_required_step_appears_only_in_a_comment(
    run_ci_sequence: RunCiSequence, fail: MakeFinding
) -> None:
    ci = _PY_CI.replace(
        "      - run: uv run --no-sync pytest\n",
        "      - run: |\n          # uv run --no-sync pytest\n          echo skipped\n",
    )
    result = run_ci_sequence(python=True, ci=ci)
    assert result.findings == [fail("python ci is missing `pytest`")]


@pytest.mark.parametrize("missing", ["", "uv sync --locked", "rumdl check", "pnpm install --frozen-lockfile"])
def test_8_6_1_requires_install_and_markdown_checks_for_tooling_only_manifests(
    run_check_with_files: RunCheckWithFiles, missing: str, fail: MakeFinding, sequence_pass: Finding
) -> None:
    steps = ("pnpm install --frozen-lockfile", "uv sync --locked", "uv run rumdl check")
    ci = "jobs:\n  ci:\n    steps:\n" + "".join(
        f"      - run: {step}\n" for step in steps if not missing or missing not in step
    )
    result = run_check_with_files(
        CHECK_ID,
        {
            "package.json": "{}",
            "pyproject.toml": "[tool.uv]\npackage = false\n",
            ".github/workflows/ci.yml": ci,
        },
    )
    label = "ts" if missing.startswith("pnpm") else "python"
    assert result.findings == ([fail(f"{label} ci is missing `{missing}`")] if missing else [sequence_pass])
