import shutil
from collections.abc import Callable
from importlib import resources
from pathlib import Path

import pytest
from cerberus import config, context
from cerberus.checks import justfile_check
from cerberus.model import CheckResult, Repo, Status

requires_just = pytest.mark.skipif(shutil.which("just") is None, reason="requires the `just` binary on PATH")

RunJustfileCheck = Callable[[str | None], CheckResult]

BASELINE = resources.files("cerberus").joinpath("baseline.just").read_text()
CONFORMING = f"# BASELINE\n{BASELINE}\n# CUSTOM\n"

INSTALL_RECIPE = (
    "# Install both workspaces: bun + uv.\ninstall:\n    bun install\n    uv sync --all-packages --all-groups\n\n"
)
DEFAULT_RECIPE = "# List available recipes.\ndefault:\n    @just --list\n\n"
CLEAN_RECIPE = (
    "# Remove deps and caches from all workspaces.\n"
    "clean:\n"
    "    find . -type d \\( -name node_modules -o -name .venv -o -name __pycache__ -o -name .tsbuild"
    " -o -name dist -o -name .ruff_cache -o -name .pytest_cache -o -name .rumdl_cache \\)"
    " -prune -exec rm -rf {} +\n"
    "    find . -type f \\( -name '*.tsbuildinfo' -o -name '.eslintcache' -o -name '*.py[cod]' \\) -delete\n"
)

UNPARSEABLE = "recipe without colon\n"
MISSING_REQUIRED_ALIAS = CONFORMING.replace("alias k := knip\n", "")
WRONG_ALIAS_TARGET = CONFORMING.replace("alias k := knip\n", "alias k := lint\n")
MISSING_REQUIRED_RECIPE = CONFORMING.replace(DEFAULT_RECIPE, "")
MISSING_RECOMMENDED = CONFORMING.replace("alias ui := upgrade-interactive\n", "").replace(CLEAN_RECIPE, "")
WRONG_CHECK_ORDER = CONFORMING.replace(
    "check: install knip typecheck lint test", "check: install lint knip typecheck test"
)
INTERLEAVED_CHECK = CONFORMING.replace(
    "check: install knip typecheck lint test", "check: install knip build typecheck lint test"
) + ("\nbuild:\n    bun run build\n")
DEFAULT_NO_LIST = CONFORMING.replace("default:\n    @just --list\n", "default:\n    @echo hi\n")
BARE_TOOL_CALL = CONFORMING.replace("    uv run rumdl check --fix\n", "    rumdl check\n")
WITH_MODULES = CONFORMING + "\nmod infra 'infra/justfile'\nmod tools\nmod? extras\n"
DEGENERATE_MODULE_PATH = CONFORMING + "\nmod infra ''\n"
NO_CERBERUS_RUN = CONFORMING.replace("    uv run cerberus --fix\n", "")
CERBERUS_IN_CHECK_BODY = NO_CERBERUS_RUN.replace(
    "check: install knip typecheck lint test",
    "check: install knip typecheck lint test\n    uv run cerberus --fix",
)
CERBERUS_ONLY_MENTIONED = NO_CERBERUS_RUN.replace(
    "    bun run lint:fix\n",
    "    # cerberus runs in ci\n    echo cerberus\n    bun run lint:fix\n",
)
CUSTOM_TAIL_TRAILING_WS = CONFORMING + "\nsmoke:\n    echo ok   \n"
CUSTOM_TAIL_TRAILING_WS_LINE = CUSTOM_TAIL_TRAILING_WS.count("\n")
WITH_INTERPOLATION = CONFORMING + (
    '\nrecipe := "examples/recipe.toml"\n\nup *args:\n    uv run totchef up --recipe {{ recipe }} {{ args }}\n'
)
NO_MARKERS = CONFORMING.replace("# BASELINE\n", "").replace("# CUSTOM\n", "")
DRIFTED_INSTALL = CONFORMING.replace("    bun install\n", "    bun install --frozen-lockfile\n")
DRIFTED_INSTALL_LINE = DRIFTED_INSTALL.splitlines().index("    bun install --frozen-lockfile") + 1
DRIFTED_WITH_TAIL = DRIFTED_INSTALL + "\nsmoke:\n    echo ok\n"
UNFIXABLE_DUPLICATE_RECIPE = CONFORMING.replace(INSTALL_RECIPE, "") + "\ninstall:\n    bun install\n"
FREE_FORM_CUSTOM_TAIL = CONFORMING + (
    "\nset dotenv-load := true\n\ngreeting := 'hello'\n\nalias s := smoke\n\n"
    "# Smoke-test the checkout.\nsmoke:\n    echo {{ greeting }}\n"
)


def baseline_messages(result: CheckResult) -> list[str]:
    return [f.message for f in result.problems if f.message.startswith("baseline")]


def structural_messages(result: CheckResult) -> list[str]:
    return [f.message for f in result.problems if not f.message.startswith("baseline")]


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


def run_fixing_justfile_check(tmp_path: Path, justfile_text: str) -> CheckResult:
    (tmp_path / "justfile").write_text(justfile_text)
    fixer = context.local_context(config.load(), tmp_path, fix=True)
    return justfile_check.run(fixer.repos()[0], fixer)


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
    run_justfile_check: RunJustfileCheck, justfile_text: str, expected_message: str
) -> None:
    result = run_justfile_check(justfile_text)
    assert (result.status, structural_messages(result)) == (Status.FAIL, [expected_message])


@requires_just
def test_1_2_2_fails_when_a_required_recipe_is_missing(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(MISSING_REQUIRED_RECIPE)
    assert (result.status, structural_messages(result)) == (Status.FAIL, ["missing required recipe `default`"])


@requires_just
def test_1_2_3_fails_when_a_recommended_alias_or_recipe_is_missing(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(MISSING_RECOMMENDED)
    assert (result.status, structural_messages(result)) == (
        Status.FAIL,
        ["missing recommended alias `ui := upgrade-interactive`", "missing recommended recipe `clean`"],
    )


@requires_just
def test_1_3_1_fails_when_the_check_recipe_runs_its_steps_out_of_order(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(WRONG_CHECK_ORDER)
    assert (result.status, structural_messages(result)) == (
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
    assert structural_messages(result) == []


@requires_just
def test_1_4_1_fails_when_the_default_recipe_does_not_list_available_commands(
    run_justfile_check: RunJustfileCheck,
) -> None:
    result = run_justfile_check(DEFAULT_NO_LIST)
    assert (result.status, structural_messages(result)) == (Status.FAIL, ["`default` recipe should run `just --list`"])


@requires_just
def test_1_5_1_fails_and_names_the_tool_when_a_recipe_calls_it_directly(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(BARE_TOOL_CALL)
    assert (result.status, structural_messages(result)) == (
        Status.FAIL,
        ["recipe `lint` runs `rumdl` directly; managed tools must run via `uv run`/`bunx`"],
    )


@requires_just
def test_1_6_1_fails_when_a_recipe_line_has_trailing_whitespace(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(CUSTOM_TAIL_TRAILING_WS)
    assert (result.status, structural_messages(result)) == (
        Status.FAIL,
        [f"trailing whitespace on line(s) {CUSTOM_TAIL_TRAILING_WS_LINE}"],
    )


@requires_just
def test_1_6_2_strips_trailing_whitespace_when_run_with_fix(tmp_path: Path) -> None:
    result = run_fixing_justfile_check(tmp_path, CUSTOM_TAIL_TRAILING_WS)
    assert (tmp_path / "justfile").read_text() == CONFORMING + "\nsmoke:\n    echo ok\n"
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
def test_1_8_2_errors_instead_of_crashing_on_a_module_with_a_degenerate_path(
    run_justfile_check: RunJustfileCheck,
) -> None:
    result = run_justfile_check(DEGENERATE_MODULE_PATH)
    assert result.status is Status.ERROR
    assert result.problems[-1].message.startswith("could not parse justfile: ")


@requires_just
def test_1_9_1_fails_when_no_recipe_in_the_check_pipeline_runs_cerberus(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(NO_CERBERUS_RUN)
    assert (result.status, structural_messages(result)) == (
        Status.FAIL,
        ["no recipe reachable from `check` runs cerberus; add `uv run cerberus --fix` to `lint`"],
    )


@requires_just
def test_1_9_2_counts_a_cerberus_run_in_the_check_recipe_body_itself(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(CERBERUS_IN_CHECK_BODY)
    assert structural_messages(result) == []


@requires_just
def test_1_9_3_does_not_count_a_mere_mention_of_cerberus(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(CERBERUS_ONLY_MENTIONED)
    assert (result.status, structural_messages(result)) == (
        Status.FAIL,
        ["no recipe reachable from `check` runs cerberus; add `uv run cerberus --fix` to `lint`"],
    )


@requires_just
@pytest.mark.parametrize(
    "invocation",
    [
        "uv run cerberus --fix",
        "uv run --active cerberus --fix",
        "uvx --from zyplux-cerberus cerberus --fix",
    ],
)
def test_1_9_4_counts_runner_wrapped_cerberus_invocations(
    run_justfile_check: RunJustfileCheck, invocation: str
) -> None:
    result = run_justfile_check(CONFORMING.replace("uv run cerberus --fix", invocation))
    assert structural_messages(result) == []


@requires_just
def test_1_10_1_fails_when_the_baseline_markers_are_missing(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(NO_MARKERS)
    assert result.status is Status.FAIL
    assert baseline_messages(result) == [
        (
            "baseline markers missing: line 1 must be `# BASELINE`, followed by the canonical baseline block "
            "(packaged with cerberus as `baseline.just`; see zyplux/justfile), then a `# CUSTOM` line — "
            "everything after `# CUSTOM` stays repo-specific"
        )
    ]


@requires_just
def test_1_10_2_fails_naming_the_first_line_that_drifts_from_the_canonical_baseline(
    run_justfile_check: RunJustfileCheck,
) -> None:
    result = run_justfile_check(DRIFTED_INSTALL)
    assert result.status is Status.FAIL
    assert baseline_messages(result) == [
        (
            f"baseline drift at line {DRIFTED_INSTALL_LINE}: "
            "expected `    bun install`, actual `    bun install --frozen-lockfile`"
        )
    ]


@requires_just
def test_1_10_3_rewrites_a_drifted_baseline_region_when_run_with_fix(tmp_path: Path) -> None:
    result = run_fixing_justfile_check(tmp_path, DRIFTED_WITH_TAIL)
    assert (tmp_path / "justfile").read_text() == CONFORMING + "\nsmoke:\n    echo ok\n"
    assert (result.status, result.problems) == (Status.PASS, [])


@requires_just
def test_1_10_4_refuses_to_fix_a_baseline_whose_rewrite_does_not_parse(tmp_path: Path) -> None:
    result = run_fixing_justfile_check(tmp_path, UNFIXABLE_DUPLICATE_RECIPE)
    assert (tmp_path / "justfile").read_text() == UNFIXABLE_DUPLICATE_RECIPE
    assert result.status is Status.FAIL
    assert baseline_messages(result)[0].startswith("baseline region not rewritten: the fixed justfile does not parse")


@requires_just
def test_1_10_5_leaves_the_custom_section_free_form(run_justfile_check: RunJustfileCheck) -> None:
    result = run_justfile_check(FREE_FORM_CUSTOM_TAIL)
    assert (result.status, result.problems) == (Status.PASS, [])


@requires_just
def test_1_10_6_keeps_this_repo_justfile_identical_to_the_packaged_canonical() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    checker = context.local_context(config.load(), repo_root)
    result = justfile_check.run(checker.repos()[0], checker)
    assert (result.status, result.problems) == (Status.PASS, [])
