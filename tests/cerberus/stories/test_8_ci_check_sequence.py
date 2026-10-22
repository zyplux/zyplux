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
    "      - uses: actions/checkout@v7\n"
    "      - uses: ./setup-pm\n"
    "      - run: uv run --no-sync vulture\n"
    "      - run: uv run --no-sync rumdl check\n"
    "      - run: uv run --no-sync ruff check\n"
    "      - run: uv run --no-sync ruff format --check\n"
    "      - run: uv run --no-sync pyrefly check\n"
    "      - run: uv run --no-sync pytest\n"
)
_TS_CI = (
    "jobs:\n  ci:\n    steps:\n"
    "      - uses: actions/checkout@v7\n"
    "      - uses: ./setup-pm\n"
    "      - run: pnpm run knip\n"
    "      - run: pnpm run typecheck\n"
    "      - run: pnpm run lint\n"
    "      - run: pnpm exec prettier --check .\n"
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
        (_PY_CI.replace("uv run --no-sync vulture", "uv run vulture"), "vulture"),
    ],
    ids=["step_missing", "runner_command_wrong"],
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
        "      - uses: actions/checkout@v7\n"
        "      - uses: ./setup-pm\n"
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


@pytest.mark.parametrize(
    ("ci", "missing_step"),
    [
        (_TS_CI.replace("      - run: pnpm run knip\n", ""), "pnpm run knip"),
        (_TS_CI.replace("pnpm exec prettier", "pnpx prettier"), "prettier --check"),
    ],
)
def test_8_4_2_fails_when_a_required_ts_step_is_missing_or_does_not_match_its_required_command(
    run_ci_sequence: RunCiSequence, ci: str, missing_step: str, fail: MakeFinding
) -> None:
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [fail(f"ts ci is missing `{missing_step}`")]


def test_8_4_3_fails_when_the_required_ts_steps_run_out_of_canonical_order(
    run_ci_sequence: RunCiSequence, fail: MakeFinding
) -> None:
    ci = (
        "jobs:\n  ci:\n    steps:\n"
        "      - uses: actions/checkout@v7\n"
        "      - uses: ./setup-pm\n"
        "      - run: pnpm run typecheck\n"
        "      - run: pnpm run knip\n"
        "      - run: pnpm run lint\n"
        "      - run: pnpm exec prettier --check .\n"
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


@pytest.mark.parametrize(
    "command",
    [
        "pnpm run lint:mermaid",
        "echo pnpm run lint",
        "printf '%s' 'pnpm run lint'",
        "pnpm run lint --help",
        "pnpm run lint --version",
        'pnpm run "lint"',
        "pnpm run lint $FLAGS",
    ],
)
def test_8_5_2_requires_canonical_commands_at_command_boundaries(
    run_ci_sequence: RunCiSequence, command: str, fail: MakeFinding
) -> None:
    ci = _TS_CI.replace("pnpm run lint", command)
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [fail("ts ci is missing `pnpm run lint`")]


def test_8_5_3_checks_order_using_the_canonical_invocation(run_ci_sequence: RunCiSequence, fail: MakeFinding) -> None:
    ci = _TS_CI.replace("pnpm run lint", "pnpm run lint:mermaid").replace(
        "      - run: pnpm run test", "      - run: pnpm run lint\n      - run: pnpm run test"
    )
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [
        fail(
            "ts ci steps run out of canonical order; expected ['pnpm install --frozen-lockfile', 'pnpm run knip', "
            "'pnpm run typecheck', 'pnpm run lint', 'prettier --check', 'pnpm run test']"
        )
    ]


def test_8_5_4_requires_one_canonical_command_per_ci_step(run_ci_sequence: RunCiSequence, fail: MakeFinding) -> None:
    ci = _TS_CI.replace(
        "      - run: pnpm run lint\n      - run: pnpm exec prettier --check .",
        "      - run: |\n          pnpm run lint\n          pnpm exec prettier --check .",
    )
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [
        fail("ts ci is missing `pnpm run lint`"),
        fail("ts ci is missing `prettier --check`"),
    ]


@pytest.mark.parametrize(
    "command",
    [
        "pnpm run lint || true",
        "pnpm run lint &",
        "false && pnpm run lint",
        "pnpm run lint && true",
        "if true; then set +e; fi; pnpm run lint",
    ],
)
def test_8_5_5_rejects_skipped_background_or_chained_commands(
    run_ci_sequence: RunCiSequence, command: str, fail: MakeFinding
) -> None:
    result = run_ci_sequence(ts=True, ci=_TS_CI.replace("pnpm run lint", command))
    assert result.findings == [fail("ts ci is missing `pnpm run lint`")]


@pytest.mark.parametrize("missing", ["", "rumdl check"])
def test_8_6_1_requires_install_and_markdown_checks_for_tooling_only_manifests(
    run_check_with_files: RunCheckWithFiles, missing: str, fail: MakeFinding, sequence_pass: Finding
) -> None:
    ci = "jobs:\n  ci:\n    steps:\n      - uses: actions/checkout@v7\n      - uses: ./setup-pm\n"
    if not missing:
        ci += "      - run: uv run --no-sync rumdl check\n"
    result = run_check_with_files(
        CHECK_ID,
        {
            "package.json": "{}",
            "pyproject.toml": "[tool.uv]\npackage = false\n",
            ".github/workflows/ci.yml": ci,
        },
    )
    assert result.findings == ([fail(f"python ci is missing `{missing}`")] if missing else [sequence_pass])


def test_8_6_2_requires_python_quality_steps_for_stub_only_packages(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    result = run_check_with_files(
        CHECK_ID,
        {
            "app.pyi": "",
            "pyproject.toml": "[project]\nname = 'sample-stubs'\nversion = '0.0.0'\n",
            ".github/workflows/ci.yml": _PY_CI.replace("      - run: uv run --no-sync pyrefly check\n", ""),
        },
    )
    assert result.findings == [fail("python ci is missing `pyrefly check`")]


@pytest.mark.parametrize("path", ["eslint.config.ts", "vitest.config.ts"])
def test_8_6_3_requires_typescript_quality_steps_for_executable_tool_configuration(
    run_check_with_files: RunCheckWithFiles, path: str, fail: MakeFinding
) -> None:
    result = run_check_with_files(
        CHECK_ID,
        {
            path: "export default {};\n",
            "package.json": "{}",
            ".github/workflows/ci.yml": (
                "jobs:\n  ci:\n    steps:\n      - uses: actions/checkout@v7\n"
                "      - uses: ./setup-pm\n      - run: pnpm exec prettier --check .\n"
            ),
        },
    )
    assert result.findings == [
        fail(f"ts ci is missing `pnpm run {script}`") for script in ("knip", "typecheck", "lint", "test")
    ]


def test_8_6_4_does_not_require_prettier_for_javascript_tool_configuration(
    run_check_with_files: RunCheckWithFiles, sequence_pass: Finding
) -> None:
    result = run_check_with_files(
        CHECK_ID,
        {
            "eslint.config.js": "export default {};\n",
            "package.json": "{}",
            ".github/workflows/ci.yml": (
                "jobs:\n  ci:\n    steps:\n      - uses: actions/checkout@v7\n      - uses: ./setup-pm\n"
            ),
        },
    )
    assert result.findings == [sequence_pass]


@pytest.mark.parametrize("option", ["--min-severity error", "--min-severity=error", "--min-severity=warn"])
def test_8_5_6_rejects_pyrefly_warning_threshold_overrides(
    run_ci_sequence: RunCiSequence, fail: MakeFinding, option: str
) -> None:
    result = run_ci_sequence(python=True, ci=_PY_CI.replace("pyrefly check", f"pyrefly check {option}"))

    assert result.findings == [fail("python ci is missing `pyrefly check`")]


@pytest.mark.parametrize("action", ["./setup-pm", "zyplux/zyplux/setup-pm@main", "zyplux/zyplux/setup-pm@abc123"])
def test_8_7_1_accepts_both_locked_installs_from_the_shared_action(
    run_ci_sequence: RunCiSequence, sequence_pass: Finding, action: str
) -> None:
    ci = _TS_CI.replace("./setup-pm", action)
    ci += _PY_CI.split("      - uses: actions/checkout@v7\n      - uses: ./setup-pm\n", 1)[1]
    result = run_ci_sequence(ts=True, python=True, ci=ci)
    assert result.findings == [sequence_pass]


@pytest.mark.parametrize(
    "setup",
    [
        "run: pnpm install --frozen-lockfile",
        "uses: pnpm/setup@v3\n        with: {require-lockfile: true}",
        "uses: zyplux/zyplux/setup-pm@",
        "uses: other/zyplux/setup-pm@main",
        "uses: false",
    ],
)
def test_8_7_2_requires_the_shared_action_even_with_a_manual_frozen_install(
    run_ci_sequence: RunCiSequence, fail: MakeFinding, setup: str
) -> None:
    ci = _TS_CI.replace("uses: ./setup-pm", setup)
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [
        fail("ci.yml must use zyplux/zyplux/setup-pm@<ref> or ./setup-pm unconditionally before checks")
    ]


def test_8_7_3_requires_shared_setup_before_quality_checks(run_ci_sequence: RunCiSequence, fail: MakeFinding) -> None:
    ci = _TS_CI.replace("      - uses: actions/checkout@v7\n      - uses: ./setup-pm\n", "")
    ci += "      - uses: actions/checkout@v7\n      - uses: ./setup-pm\n"
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [
        fail(
            "ts ci steps run out of canonical order; expected ['pnpm install --frozen-lockfile', 'pnpm run knip', "
            "'pnpm run typecheck', 'pnpm run lint', 'prettier --check', 'pnpm run test']"
        )
    ]


@pytest.mark.parametrize("setting", ["if: false", "if: '${{ inputs.setup }}'", "continue-on-error: true"])
def test_8_7_4_requires_unconditional_successful_setup(
    run_ci_sequence: RunCiSequence, fail: MakeFinding, setting: str
) -> None:
    ci = _TS_CI.replace("uses: ./setup-pm", f"uses: ./setup-pm\n        {setting}")
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [
        fail("ci.yml must use zyplux/zyplux/setup-pm@<ref> or ./setup-pm unconditionally before checks")
    ]


@pytest.mark.parametrize(
    ("ci", "message"),
    [
        (
            _TS_CI.replace("  ci:\n", "  prepare:\n") + "  ci:\n    steps:\n      - run: pnpm run test\n",
            "ci.yml must use zyplux/zyplux/setup-pm@<ref> or ./setup-pm unconditionally before checks",
        ),
        (_TS_CI.replace("  ci:\n", "  ci:\n    if: false\n"), "ci.yml must run an unconditional ci job"),
        ("jobs: []", "ci.yml must run an unconditional ci job"),
    ],
)
def test_8_7_5_requires_setup_and_checks_in_the_unconditional_ci_job(
    run_ci_sequence: RunCiSequence, fail: MakeFinding, ci: str, message: str
) -> None:
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [fail(message)]


@pytest.mark.parametrize(
    "ci",
    [
        _TS_CI.replace("      - uses: actions/checkout@v7\n", ""),
        _TS_CI.replace("uses: actions/checkout@v7", "uses: actions/checkout@v7\n        if: false"),
        _TS_CI.replace("actions/checkout@v7", "actions/checkout@"),
        _TS_CI.replace("uses: actions/checkout@v7", "uses: actions/checkout@v7\n        with: {path: source}"),
        _TS_CI.replace("      - uses: actions/checkout@v7\n", "") + "      - uses: actions/checkout@v7\n",
    ],
)
def test_8_7_6_requires_root_checkout_before_shared_setup(
    run_ci_sequence: RunCiSequence, fail: MakeFinding, ci: str
) -> None:
    result = run_ci_sequence(ts=True, ci=ci)
    assert result.findings == [
        fail("ci job must check out the repository root with actions/checkout@<ref> before shared setup")
    ]


def test_8_7_7_accepts_a_ci_display_name_on_another_job_id(
    run_ci_sequence: RunCiSequence, sequence_pass: Finding
) -> None:
    ci = _TS_CI.replace("  ci:\n", "  checks:\n    name: ci\n")
    assert run_ci_sequence(ts=True, ci=ci).findings == [sequence_pass]


@pytest.mark.parametrize("path", ["", ".", "./"])
def test_8_7_8_accepts_explicit_root_checkout_paths(
    run_ci_sequence: RunCiSequence, sequence_pass: Finding, path: str
) -> None:
    ci = _TS_CI.replace("uses: actions/checkout@v7", f"uses: actions/checkout@v7\n        with: {{path: '{path}'}}")
    assert run_ci_sequence(ts=True, ci=ci).findings == [sequence_pass]
