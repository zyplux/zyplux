import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from cerberus import config, context
from cerberus.checks import justfile_check
from cerberus.model import CheckResult, Repo, Status

requires_just = pytest.mark.skipif(shutil.which("just") is None, reason="requires the `just` binary on PATH")

RunJustfileCheck = Callable[[str | None], CheckResult]

CONFORMING = """
alias i := install
alias k := knip
alias tc := typecheck
alias l := lint
alias t := test
alias c := check
alias u := upgrade
alias ui := upgrade-interactive

default:
    @just --list
install:
    bun install
knip:
    bun run knip
typecheck:
    bun run typecheck
lint:
    bun run lint
    uv run cerberus --fix
test:
    bun run test
check: install knip typecheck lint test
upgrade:
    bun run upgrade
upgrade-interactive:
    bun run upgrade -- -i
clean:
    rm -rf node_modules
"""

UNPARSEABLE = "recipe without colon\n"
MISSING_REQUIRED_ALIAS = CONFORMING.replace("alias k := knip\n", "")
WRONG_ALIAS_TARGET = CONFORMING.replace("alias k := knip\n", "alias k := lint\n")
MISSING_REQUIRED_RECIPE = CONFORMING.replace("default:\n    @just --list\n", "")
MISSING_RECOMMENDED = CONFORMING.replace("alias ui := upgrade-interactive\n", "").replace(
    "clean:\n    rm -rf node_modules\n", ""
)
WRONG_CHECK_ORDER = CONFORMING.replace(
    "check: install knip typecheck lint test", "check: install lint knip typecheck test"
)
INTERLEAVED_CHECK = CONFORMING.replace(
    "check: install knip typecheck lint test", "check: install knip build typecheck lint test"
).replace("clean:\n", "build:\n    bun run build\nclean:\n")
DEFAULT_NO_LIST = CONFORMING.replace("default:\n    @just --list\n", "default:\n    echo hi\n")
BARE_TOOL_CALL = CONFORMING.replace("lint:\n    bun run lint\n", "lint:\n    rumdl check\n")
WITH_MODULES = CONFORMING + "\nmod infra 'infra/justfile'\nmod tools\nmod? extras\n"
NO_CERBERUS_RUN = CONFORMING.replace("    uv run cerberus --fix\n", "")
CERBERUS_IN_CHECK_BODY = NO_CERBERUS_RUN.replace(
    "check: install knip typecheck lint test",
    "check: install knip typecheck lint test\n    uv run cerberus --fix",
)
TRAILING_WHITESPACE = CONFORMING.replace(
    "check: install knip typecheck lint test\n",
    "check: install knip typecheck lint test   \n",
)

WITH_INTERPOLATION = CONFORMING + (
    '\nrecipe := "examples/recipe.toml"\n\nup *args:\n    uv run totchef up --recipe {{ recipe }} {{ args }}\n'
)


@pytest.fixture
def repo() -> Repo:
    return Repo("demo")


@pytest.fixture
def ctx() -> context.Context:
    return context.local_context(config.load(), Path())


@pytest.fixture
def run_justfile_check(monkeypatch: pytest.MonkeyPatch, repo: Repo, ctx: context.Context) -> RunJustfileCheck:
    def _run(justfile_text: str | None) -> CheckResult:
        monkeypatch.setattr(ctx, "file", lambda *_: justfile_text)
        return justfile_check.run(repo, ctx)

    return _run


@requires_just
def test_1_1_1_passes_a_fully_conforming_justfile(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(CONFORMING)
    assert (result.status, result.problems) == (Status.PASS, [])


def test_1_1_2_fails_when_the_repo_has_no_justfile_at_its_root(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(None)
    assert (result.status, [f.message for f in result.problems]) == (Status.FAIL, ["no justfile at repo root"])


@requires_just
def test_1_1_3_errors_when_the_justfile_cannot_be_parsed(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(UNPARSEABLE)
    assert result.status is Status.ERROR
    assert result.problems[0].message.startswith("could not parse justfile: ")


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
    run_justfile_check: RunJustfileCheck, justfile_text: str, expected_message: str
) -> None:
    result = run_justfile_check(justfile_text)
    assert (result.status, [f.message for f in result.problems]) == (Status.FAIL, [expected_message])


@requires_just
def test_1_2_2_fails_when_a_required_recipe_is_missing(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(MISSING_REQUIRED_RECIPE)
    assert (result.status, [f.message for f in result.problems]) == (
        Status.FAIL,
        ["missing required recipe `default`"],
    )


@requires_just
def test_1_2_3_fails_when_a_recommended_alias_or_recipe_is_missing(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(MISSING_RECOMMENDED)
    assert (result.status, [f.message for f in result.problems]) == (
        Status.FAIL,
        ["missing recommended alias `ui := upgrade-interactive`", "missing recommended recipe `clean`"],
    )


@requires_just
def test_1_3_1_fails_when_the_check_recipe_runs_its_steps_out_of_order(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(WRONG_CHECK_ORDER)
    assert (result.status, [f.message for f in result.problems]) == (
        Status.FAIL,
        [
            (
                "`check` dependencies ['install', 'lint', 'knip', 'typecheck', 'test'] "
                "must contain ['install', 'knip', 'typecheck', 'lint', 'test'] in order"
            )
        ],
    )


@requires_just
def test_1_3_2_passes_when_extra_steps_are_interleaved_between_the_pipeline_steps(
    run_justfile_check: RunJustfileCheck,
) -> None:
    result = run_justfile_check(INTERLEAVED_CHECK)
    assert (result.status, result.problems) == (Status.PASS, [])


@requires_just
def test_1_4_1_fails_when_the_default_recipe_does_not_list_available_commands(
    run_justfile_check: RunJustfileCheck,
) -> None:
    result = run_justfile_check(DEFAULT_NO_LIST)
    assert (result.status, [f.message for f in result.problems]) == (
        Status.FAIL,
        ["`default` recipe should run `just --list`"],
    )


@requires_just
def test_1_5_1_fails_and_names_the_tool_when_a_recipe_calls_it_directly(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(BARE_TOOL_CALL)
    assert (result.status, [f.message for f in result.problems]) == (
        Status.FAIL,
        ["recipe `lint` runs `rumdl` directly; managed tools must run via `uv run`/`bunx`"],
    )


@requires_just
def test_1_6_1_fails_when_a_recipe_line_has_trailing_whitespace(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(TRAILING_WHITESPACE)
    assert (result.status, [f.message for f in result.problems]) == (
        Status.FAIL,
        ["trailing whitespace on line(s) 24"],
    )


@requires_just
def test_1_6_2_strips_trailing_whitespace_when_run_with_fix(tmp_path: Path) -> None:
    (tmp_path / "justfile").write_text(TRAILING_WHITESPACE)
    fixer = context.local_context(config.load(), tmp_path, fix=True)
    result = justfile_check.run(fixer.repos()[0], fixer)
    assert (tmp_path / "justfile").read_text() == CONFORMING
    assert (result.status, result.problems) == (Status.PASS, [])


@requires_just
def test_1_7_1_passes_a_conforming_justfile_whose_recipes_use_interpolation(
    run_justfile_check: RunJustfileCheck,
) -> None:
    result = run_justfile_check(WITH_INTERPOLATION)
    assert (result.status, result.problems) == (Status.PASS, [])


@requires_just
def test_1_8_1_passes_a_conforming_justfile_that_declares_modules(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(WITH_MODULES)
    assert (result.status, result.problems) == (Status.PASS, [])


@requires_just
def test_1_9_1_fails_when_no_recipe_in_the_check_pipeline_runs_cerberus(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(NO_CERBERUS_RUN)
    assert (result.status, [f.message for f in result.problems]) == (
        Status.FAIL,
        ["no recipe reachable from `check` runs cerberus; add `uv run cerberus --fix` to `lint`"],
    )


@requires_just
def test_1_9_2_counts_a_cerberus_run_in_the_check_recipe_body_itself(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(CERBERUS_IN_CHECK_BODY)
    assert (result.status, result.problems) == (Status.PASS, [])
