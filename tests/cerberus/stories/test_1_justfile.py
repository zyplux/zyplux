from __future__ import annotations

import os
import shutil
import subprocess
from importlib import resources
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from cerberus.model import CheckResult, Status
    from seam_fixtures import RunCheckOnDisk, RunCheckWithFiles

type RunJustfileCheck = Callable[[str | None], CheckResult]

requires_just = pytest.mark.skipif(shutil.which("just") is None, reason="requires the `just` binary on PATH")

BASELINE = resources.files("cerberus").joinpath("baseline.just").read_text()
CONFORMING = f"# BASELINE\n{BASELINE}\n# CUSTOM\n"

DEFAULT_RECIPE = "# List available recipes.\ndefault:\n    @just --list\n\n"
CLEAN_RECIPE = (
    "# Remove gitignored build artifacts and caches from all workspaces.\n"
    "clean *flags:\n    pnpm run cz clean {{ flags }}\n"
)

UNPARSEABLE = "recipe without colon\n"
MISSING_REQUIRED_ALIAS = CONFORMING.replace("alias k := knip\n", "")
WRONG_ALIAS_TARGET = CONFORMING.replace("alias k := knip\n", "alias k := lint\n")
MISSING_REQUIRED_RECIPE = CONFORMING.replace(DEFAULT_RECIPE, "")
MISSING_RECOMMENDED = CONFORMING.replace("alias ui := upgrade-interactive\n", "").replace(CLEAN_RECIPE, "")
WRONG_CHECK_ORDER = CONFORMING.replace(
    "check: install knip typecheck lint test cerberus",
    "check: install lint knip typecheck test cerberus",
)
INTERLEAVED_CHECK = CONFORMING.replace(
    "check: install knip typecheck lint test cerberus",
    "check: install knip extra typecheck lint test cerberus",
) + ("\nextra:\n    echo extra\n")
DEFAULT_NO_LIST = CONFORMING.replace("default:\n    @just --list\n", "default:\n    @echo hi\n")
BARE_TOOL_CALL = CONFORMING.replace("    uv run rumdl check --fix\n", "    rumdl check\n")
WITH_MODULES = CONFORMING + (
    "\nmod infra 'infra/justfile'\nmod tools\nmod? extras\n"
    "mod member-idp 'infra/member-idp/justfile'\nmod workflow-tools\nmod? e2e-tests\n"
)
DEGENERATE_MODULE_PATH = CONFORMING + "\nmod infra ''\n"
NO_CERBERUS_RUN = CONFORMING.replace("    uv run cerberus --fix\n", "")
CERBERUS_IN_CHECK_BODY = NO_CERBERUS_RUN.replace(
    "check: install knip typecheck lint test cerberus",
    "check: install knip typecheck lint test cerberus\n    uv run cerberus --fix",
)
CERBERUS_ONLY_MENTIONED = NO_CERBERUS_RUN.replace(
    "    pnpm run lint:fix\n",
    "    # cerberus runs in ci\n    echo cerberus\n    pnpm run lint:fix\n",
)
CLEAN_WITHOUT_CZ = CONFORMING.replace(CLEAN_RECIPE, "clean:\n    rm -rf node_modules dist\n")
CLEAN_RUNS_BARE_CZ = CONFORMING.replace("    pnpm run cz clean {{ flags }}\n", "    cz clean {{ flags }}\n")
CLEAN_ONLY_MENTIONED = CONFORMING.replace("    pnpm run cz clean {{ flags }}\n", '    echo "cz clean is nice"\n')
CLEAN_RUNNER_WRAPS_UNRELATED_COMMAND = CONFORMING.replace(
    "    pnpm run cz clean {{ flags }}\n", "    pnpm run echo cz clean\n"
)

CUSTOM_TAIL_TRAILING_WS = CONFORMING + "\nsmoke:\n    echo ok   \n"
CUSTOM_TAIL_TRAILING_WS_LINE = CUSTOM_TAIL_TRAILING_WS.count("\n")
WITH_INTERPOLATION = CONFORMING + (
    '\nrecipe := "examples/recipe.toml"\n\nup *args:\n    uv run totchef up --recipe {{ recipe }} {{ args }}\n'
)
NO_MARKERS = CONFORMING.replace("# BASELINE\n", "").replace("# CUSTOM\n", "")
DRIFTED_INSTALL = CONFORMING.replace("    pnpm install\n", "    pnpm install --frozen-lockfile\n")
DRIFTED_WITH_TAIL = DRIFTED_INSTALL + "\nsmoke:\n    echo ok\n"
FREE_FORM_CUSTOM_TAIL = CONFORMING + (
    "\nset dotenv-load := true\n\ngreeting := 'hello'\n\nalias s := smoke\n\n"
    "# Smoke-test the checkout.\nsmoke:\n    echo {{ greeting }}\n"
)

CHECK_ID = "justfile"
WORKSPACE_MANIFESTS = {
    "app.py": "print(1)",
    "app.ts": "console.log(1);",
    "package.json": "{}",
    "pyproject.toml": "[project]\nname = 'sample'\nversion = '0.0.0'\n",
}


@pytest.fixture
def run_justfile_check(run_check_with_files: RunCheckWithFiles) -> RunJustfileCheck:
    def _run(justfile_text: str | None) -> CheckResult:
        files = {} if justfile_text is None else {"justfile": justfile_text, **WORKSPACE_MANIFESTS}
        return run_check_with_files(CHECK_ID, files)

    return _run


@requires_just
def test_1_1_1_passes_a_fully_conforming_justfile(run_justfile_check: RunJustfileCheck, status: type[Status]) -> None:
    result = run_justfile_check(CONFORMING)
    assert (result.status, result.problems) == (status.PASS, [])


def test_1_1_2_fails_when_the_repo_has_no_justfile_at_its_root(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(None)
    assert (result.status, [f.message for f in result.problems]) == (status.FAIL, ["no justfile at repo root"])


@requires_just
def test_1_1_3_errors_when_the_justfile_cannot_be_parsed(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(UNPARSEABLE)
    assert result.status is status.ERROR
    assert result.problems[-1].message.startswith("could not parse justfile: ")


@requires_just
@pytest.mark.parametrize(
    ("justfile_text", "expected_message"),
    [
        (MISSING_REQUIRED_ALIAS, "missing alias `k := knip`"),
        (WRONG_ALIAS_TARGET, "alias `k` targets `lint`, expected `knip`"),
    ],
    ids=["missing", "wrong-target"],
)
def test_1_2_1_fails_when_a_required_alias_is_missing_or_targets_the_wrong_recipe(
    run_justfile_check: RunJustfileCheck, justfile_text: str, expected_message: str, status: type[Status]
) -> None:
    result = run_justfile_check(justfile_text)
    assert (result.status, [f.message for f in result.problems]) == (status.FAIL, [expected_message])


@requires_just
def test_1_2_2_fails_when_a_required_recipe_is_missing(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(MISSING_REQUIRED_RECIPE)
    assert (result.status, [f.message for f in result.problems]) == (status.FAIL, ["missing required recipe `default`"])


@requires_just
def test_1_2_3_fails_when_a_recommended_alias_or_recipe_is_missing(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(MISSING_RECOMMENDED)
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        ["missing recommended alias `ui := upgrade-interactive`", "missing recommended recipe `clean`"],
    )


@requires_just
def test_1_3_1_fails_when_the_check_recipe_runs_its_steps_out_of_order(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(WRONG_CHECK_ORDER)
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        [
            (
                "`check` steps ['install', 'lint', 'knip', 'typecheck', 'test', 'cerberus'] must "
                "contain ['install', 'knip', 'typecheck', 'lint', 'test'] in order"
            )
        ],
    )


@requires_just
def test_1_3_2_passes_when_extra_steps_are_interleaved_between_the_pipeline_steps(
    run_justfile_check: RunJustfileCheck,
) -> None:
    result = run_justfile_check(INTERLEAVED_CHECK)
    assert [f.message for f in result.problems] == []


@requires_just
def test_1_4_1_fails_when_the_default_recipe_does_not_list_available_commands(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(DEFAULT_NO_LIST)
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        ["`default` recipe should run `just --list`"],
    )


@requires_just
def test_1_5_1_fails_and_names_the_tool_when_a_recipe_calls_it_directly(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(BARE_TOOL_CALL)
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        [
            "recipe `lint` must run `uv run rumdl check --fix` without masking its failure",
            "recipe `lint` runs `rumdl` directly; managed tools must run via `uv run`/`pnpx`",
        ],
    )


@requires_just
def test_1_6_1_fails_when_a_recipe_line_has_trailing_whitespace(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(CUSTOM_TAIL_TRAILING_WS)
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        [f"trailing whitespace on line(s) {CUSTOM_TAIL_TRAILING_WS_LINE}"],
    )


@requires_just
def test_1_6_2_strips_trailing_whitespace_when_run_with_fix(
    run_check_on_disk: RunCheckOnDisk, tmp_path: Path, status: type[Status]
) -> None:
    result = run_check_on_disk(CHECK_ID, {"justfile": CUSTOM_TAIL_TRAILING_WS}, fix=True)
    assert (tmp_path / "justfile").read_text() == CONFORMING + "\nsmoke:\n    echo ok\n"
    assert (result.status, result.problems) == (status.PASS, [])


@requires_just
def test_1_7_1_passes_a_conforming_justfile_whose_recipes_use_interpolation(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(WITH_INTERPOLATION)
    assert (result.status, result.problems) == (status.PASS, [])


@requires_just
def test_1_8_1_passes_a_conforming_justfile_that_declares_modules(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(WITH_MODULES)
    assert (result.status, result.problems) == (status.PASS, [])


@requires_just
def test_1_8_2_errors_instead_of_crashing_on_a_module_with_a_degenerate_path(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(DEGENERATE_MODULE_PATH)
    assert result.status is status.ERROR
    assert result.problems[-1].message.startswith("could not parse justfile: ")


@requires_just
def test_1_9_1_fails_when_no_recipe_in_the_check_pipeline_runs_cerberus(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(NO_CERBERUS_RUN)
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        ["no recipe reachable from `check` runs cerberus; add `uv run cerberus --fix` to `check`'s pipeline"],
    )


@requires_just
def test_1_9_2_counts_a_cerberus_run_in_the_check_recipe_body_itself(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(CERBERUS_IN_CHECK_BODY)
    assert [f.message for f in result.problems] == []


@requires_just
def test_1_9_3_does_not_count_a_mere_mention_of_cerberus(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(CERBERUS_ONLY_MENTIONED)
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        ["no recipe reachable from `check` runs cerberus; add `uv run cerberus --fix` to `check`'s pipeline"],
    )


@requires_just
@pytest.mark.parametrize("content", [NO_MARKERS, DRIFTED_WITH_TAIL, FREE_FORM_CUSTOM_TAIL])
def test_1_10_1_accepts_application_recipes_without_rewriting_them(
    run_check_on_disk: RunCheckOnDisk, tmp_path: Path, content: str, status: type[Status]
) -> None:
    result = run_check_on_disk(CHECK_ID, {"justfile": content}, fix=True)
    assert (result.status, result.problems) == (status.PASS, [])
    assert (tmp_path / "justfile").read_text() == content


@requires_just
@pytest.mark.parametrize("calls", ["i k tc l t cerberus", "install knip typecheck lint test cerberus"])
def test_1_10_2_accepts_ordered_recipe_calls_in_a_parameterized_check_body(
    run_justfile_check: RunJustfileCheck, calls: str, status: type[Status]
) -> None:
    body = "check name='':\n" + "".join(f"    @just {recipe}\n" for recipe in calls.split())
    content = CONFORMING.replace("check: install knip typecheck lint test cerberus", body.rstrip())
    result = run_justfile_check(content)
    assert (result.status, result.problems) == (status.PASS, [])


@requires_just
def test_1_10_3_rejects_a_body_pipeline_that_skips_a_required_step(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    content = CONFORMING.replace(
        "check: install knip typecheck lint test cerberus",
        "check:\n    @just install\n    @just typecheck\n    @just lint\n    @just test\n    @just cerberus",
    )
    result = run_justfile_check(content)
    assert result.status is status.FAIL
    assert any("`check` steps" in finding.message for finding in result.problems)


@requires_just
def test_1_10_4_follows_nested_recipe_calls_without_counting_comments_or_echo_arguments(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    content = (
        CONFORMING.replace(
            "check: install knip typecheck lint test cerberus",
            "check: install knip typecheck lint test\n    @just governance",
        )
        + "\ngovernance:\n    @just cerberus\n"
    )
    assert run_justfile_check(content).status is status.PASS
    mentions = content.replace("    @just governance", "    # just governance\n    echo just governance")
    assert run_justfile_check(mentions).status is status.FAIL


@requires_just
def test_1_10_5_rejects_recursive_body_calls(run_justfile_check: RunJustfileCheck, status: type[Status]) -> None:
    content = CONFORMING.replace("check: install knip typecheck lint test cerberus", "check:\n    @just check")
    result = run_justfile_check(content)
    assert result.status is status.FAIL
    assert any("recursive just invocation" in finding.message for finding in result.problems)


@requires_just
@pytest.mark.parametrize(
    "call",
    [
        "echo just lint",
        "if false; then just lint; fi",
        "just lint | cat",
        "just lint &",
        "just lint || true",
        "-just lint",
        "false && just lint",
    ],
)
def test_1_10_6_rejects_skipped_background_or_masked_gate_steps(
    run_justfile_check: RunJustfileCheck, call: str
) -> None:
    content = CONFORMING.replace(
        "check: install knip typecheck lint test cerberus",
        f"check: install knip typecheck\n    {call}\n    just test\n    just cerberus",
    )
    assert run_justfile_check(content).problems


@requires_just
@pytest.mark.parametrize(
    "command",
    [
        "echo pnpm run lint:fix",
        "if false; then pnpm run lint:fix; fi",
        "pnpm run lint:fix | cat",
        "pnpm run lint:fix &",
        "pnpm run lint:fix || true",
        "-pnpm run lint:fix",
        "pnpm run --if-present lint:fix",
        "pnpm run --help lint:fix",
        "pnpm run lint:fix --help",
        "pnpm run lint:fix -h",
        "pnpm run lint:fix --version",
        "pnpm run lint:fix -V",
    ],
)
def test_1_10_7_requires_real_failure_preserving_tool_calls(run_justfile_check: RunJustfileCheck, command: str) -> None:
    content = CONFORMING.replace("    pnpm run lint:fix\n", f"    {command}\n")
    assert any("must run `pnpm run lint:fix`" in finding.message for finding in run_justfile_check(content).problems)


@requires_just
@pytest.mark.parametrize("recipe", ["install", "knip", "typecheck", "lint", "test"])
def test_1_10_8_rejects_empty_quality_recipes(run_justfile_check: RunJustfileCheck, recipe: str) -> None:
    lines = CONFORMING.splitlines(keepends=True)
    start = lines.index(f"{recipe}:\n")
    end = start + 1
    while end < len(lines) and (lines[end].startswith("    ") or not lines[end].strip()):
        end += 1
    content = "".join([*lines[: start + 1], "    echo no checks\n\n", *lines[end:]])
    assert run_justfile_check(content).problems


@requires_just
def test_1_10_9_follows_shell_install_helpers(run_check_with_files: RunCheckWithFiles) -> None:
    content = CONFORMING.replace(
        "    pnpm install\n    uv sync --all-packages --all-groups\n", "    bash scripts/install.sh\n"
    )
    files = {
        **WORKSPACE_MANIFESTS,
        "justfile": content,
        "scripts/install.sh": (
            "#!/bin/bash\nset -euo pipefail\npnpm install --frozen-lockfile\nuv sync --all-packages --all-groups\n"
        ),
    }
    assert not run_check_with_files(CHECK_ID, files).problems
    files["scripts/install.sh"] = "echo 'pnpm install; uv sync --all-packages --all-groups'"
    assert run_check_with_files(CHECK_ID, files).problems


@requires_just
@pytest.mark.parametrize(
    "script",
    [
        "pnpm install\nset -euo pipefail\nuv sync --all-packages --all-groups",
        "set -e\npnpm install\nuv sync --all-packages --all-groups",
        "set -euo pipefail\npnpm install\nset +e\nuv sync --all-packages --all-groups",
        "set -euo pipefail\npnpm install\nuv sync --all-packages --all-groups\nset +e",
        "set -euo pipefail\nif true; then set +e; fi\npnpm install\nuv sync --all-packages --all-groups",
    ],
)
def test_1_10_14_requires_canonical_helper_options(run_check_with_files: RunCheckWithFiles, script: str) -> None:
    content = CONFORMING.replace(
        "    pnpm install\n    uv sync --all-packages --all-groups\n", "    bash scripts/install.sh\n"
    )
    assert run_check_with_files(
        CHECK_ID, {**WORKSPACE_MANIFESTS, "justfile": content, "scripts/install.sh": f"#!/bin/bash\n{script}\n"}
    ).problems


@requires_just
def test_1_10_10_rejects_reversed_test_runners(run_justfile_check: RunJustfileCheck) -> None:
    content = CONFORMING.replace(
        "    if test -f package.json; then pnpm run test; fi\n"
        '    if test -f pyproject.toml; then uv run pytest || test "$?" -eq 5; fi',
        "    uv run pytest\n    pnpm run test",
    )
    assert any("baseline order" in finding.message for finding in run_justfile_check(content).problems)


@requires_just
def test_1_10_11_requires_both_knip_graphs(run_justfile_check: RunJustfileCheck) -> None:
    content = CONFORMING.replace("    pnpm run knip\n", "")
    assert any("must run `pnpm run knip`" in finding.message for finding in run_justfile_check(content).problems)


@requires_just
@pytest.mark.parametrize(
    "command",
    [
        'echo "uv run cerberus"',
        "uv run echo cerberus",
        "uv run --extra dev cerberus --fix",
        "uvx cerberus --fix",
        "cerberus --fix",
        "uv run cerberus || true",
        "uv run cerberus | cat",
        "uv run cerberus &",
        "uv run cerberus --help",
    ],
)
def test_1_10_12_requires_a_real_failure_preserving_cerberus_run(
    run_justfile_check: RunJustfileCheck, command: str
) -> None:
    content = CONFORMING.replace("    uv run cerberus --fix\n", f"    {command}\n")
    assert any("runs cerberus" in finding.message for finding in run_justfile_check(content).problems)


@requires_just
def test_1_10_13_ignores_tool_names_inside_quoted_text(run_justfile_check: RunJustfileCheck) -> None:
    content = CONFORMING + '\nexample:\n    echo "setup; ruff check; rumdl check"\n'
    assert not run_justfile_check(content).problems


@requires_just
def test_1_11_1_fails_when_the_clean_recipe_does_not_invoke_cz_clean(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(CLEAN_WITHOUT_CZ)
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        ["`clean` recipe does not run `cz clean`; replace hardcoded find/rm with `cz clean`"],
    )


@requires_just
def test_1_11_2_passes_when_the_clean_recipe_runs_cz_clean_via_pnpm_run(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(CONFORMING)
    assert [f.message for f in result.problems] == []


@requires_just
def test_1_11_3_passes_when_the_clean_recipe_invokes_cz_clean_directly(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(CLEAN_RUNS_BARE_CZ)
    assert [f.message for f in result.problems] == []


@requires_just
def test_1_11_4_does_not_count_a_mere_mention_of_cz_clean(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(CLEAN_ONLY_MENTIONED)
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        ["`clean` recipe does not run `cz clean`; replace hardcoded find/rm with `cz clean`"],
    )


@requires_just
def test_1_11_5_does_not_count_a_runner_wrapping_an_unrelated_command(
    run_justfile_check: RunJustfileCheck, status: type[Status]
) -> None:
    result = run_justfile_check(CLEAN_RUNNER_WRAPS_UNRELATED_COMMAND)
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        ["`clean` recipe does not run `cz clean`; replace hardcoded find/rm with `cz clean`"],
    )


def test_1_12_1_delegates_both_upgrade_modes_to_cz() -> None:
    assert "upgrade *args='':\n    pnpm run --silent cz upgrade {{ args }}" in BASELINE
    assert "upgrade-interactive:\n    @pnpm run --silent cz upgrade --interactive" in BASELINE


@requires_just
@pytest.mark.parametrize(
    ("manifests", "runner_exits", "expected_calls", "is_success"),
    [
        ([], (0, 0), [], False),
        (["package.json"], (0, 1), ["pnpm run test"], True),
        (["pyproject.toml"], (1, 0), ["uv run pytest"], True),
        (["package.json", "pyproject.toml"], (0, 0), ["pnpm run test", "uv run pytest"], True),
        (["pyproject.toml"], (0, pytest.ExitCode.NO_TESTS_COLLECTED), ["uv run pytest"], True),
        (["pyproject.toml"], (0, pytest.ExitCode.TESTS_FAILED), ["uv run pytest"], False),
        (["pyproject.toml"], (0, pytest.ExitCode.INTERRUPTED), ["uv run pytest"], False),
        (["pyproject.toml"], (0, pytest.ExitCode.INTERNAL_ERROR), ["uv run pytest"], False),
        (["pyproject.toml"], (0, pytest.ExitCode.USAGE_ERROR), ["uv run pytest"], False),
        (["package.json", "pyproject.toml"], (1, 0), ["pnpm run test"], False),
        (["package.json", "pyproject.toml"], (pytest.ExitCode.NO_TESTS_COLLECTED, 0), ["pnpm run test"], False),
    ],
)
def test_1_13_1_runs_present_workspaces_sequentially_and_preserves_failures(
    tmp_path: Path, manifests: list[str], runner_exits: tuple[int, int], expected_calls: list[str], *, is_success: bool
) -> None:
    (tmp_path / "justfile").write_text(BASELINE)
    for manifest in manifests:
        (tmp_path / manifest).touch()
    executables = tmp_path / "bin"
    executables.mkdir()
    calls = tmp_path / "suite-calls.log"
    for runner, exit_code in zip(("pnpm", "uv"), runner_exits, strict=True):
        executable = executables / runner
        executable.write_text(f'#!/bin/sh\nprintf "%s\\n" "{runner} $*" >> "$ZYPLUX_SUITE_LOG"\nexit {exit_code}\n')
        executable.chmod(0o755)
    completed = subprocess.run(
        ["just", "test"],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{executables}{os.pathsep}{os.environ['PATH']}", "ZYPLUX_SUITE_LOG": str(calls)},
        check=False,
        capture_output=True,
        text=True,
    )
    assert (completed.returncode == 0) is is_success, completed.stderr
    assert (calls.read_text().splitlines() if calls.exists() else []) == expected_calls


@pytest.mark.parametrize("source", ["", "app.pyi"])
def test_1_16_1_requires_application_recipes_when_python_stubs_are_present(
    run_check_with_files: RunCheckWithFiles,
    source: str,
) -> None:
    content = CONFORMING
    for recipe, alias in (("knip", "k"), ("typecheck", "tc"), ("test", "t")):
        content = content.replace(f"alias {alias} := {recipe}\n", "")
        body = content.split(f"\n{recipe}:\n", 1)[1].split("\n\n", 1)[0]
        content = content.replace(f"\n{recipe}:\n{body}\n", "")
    content = content.replace("check: install knip typecheck lint test cerberus", "check: install lint cerberus")
    content = content.replace("    pnpm run lint:fix\n", "").replace("    pnpm run format\n", "")
    content = content.replace("    uv run ruff check --fix\n", "").replace("    uv run ruff format\n", "")
    result = run_check_with_files(
        CHECK_ID,
        {
            "justfile": content,
            "package.json": "{}",
            "pyproject.toml": "[tool.uv]\npackage = false\n",
            **({source: ""} if source else {}),
        },
    )
    assert bool(result.problems) is bool(source)
    if source:
        assert "missing required recipe `typecheck`" in [problem.message for problem in result.problems]
