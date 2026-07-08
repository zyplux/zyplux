from __future__ import annotations

import shutil
from importlib import resources
from typing import TYPE_CHECKING

import pytest
from cerberus import __version__
from cerberus.cli import app
from typer.testing import CliRunner

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo
    from typer.testing import Result

type RegisterFakeCheck = Callable[[str, Callable[[Repo, Context], CheckResult]], None]

runner = CliRunner()

USAGE_ERROR_EXIT = 2

requires_just = pytest.mark.skipif(shutil.which("just") is None, reason="requires the `just` binary on PATH")

BASELINE_JUST = resources.files("cerberus").joinpath("baseline.just").read_text()
CONFORMING_JUSTFILE = f"# BASELINE\n{BASELINE_JUST}\n# CUSTOM\n"

JUSTFILE_WITH_TRAILING_WS = CONFORMING_JUSTFILE.replace(
    "check: install knip typecheck lint test\n",
    "check: install knip typecheck lint test   \n",
)

CONFORMING_CI = """\
on:
  pull_request:
  push:
    branches: [main]
jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - run: echo ci
      - run: uvx zyplux-cerberus
"""

CONFORMING_CODEOWNERS = """\
* @zyplux/maintainers
/.github/ @zyplux/admins
"""


@pytest.fixture
def conforming_repo(tmp_path: Path, rumdl_canonical: str) -> Path:
    (tmp_path / "justfile").write_text(CONFORMING_JUSTFILE)
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(CONFORMING_CI)
    (tmp_path / ".github" / "CODEOWNERS").write_text(CONFORMING_CODEOWNERS)
    (tmp_path / ".rumdl.toml").write_text(rumdl_canonical)
    return tmp_path


@pytest.fixture
def invoke_lint(conforming_repo: Path) -> Callable[..., Result]:
    def invoke(*args: str) -> Result:
        return runner.invoke(app, [str(conforming_repo), *args])

    return invoke


@requires_just
def test_16_1_1_passes_a_fully_conforming_checkout_given_an_explicit_path(invoke_lint: Callable[..., Result]) -> None:
    result = invoke_lint()
    assert result.exit_code == 0, result.output
    assert "all bites pass" in result.output


@requires_just
def test_16_1_2_defaults_to_the_current_directory_when_no_path_argument_is_given(
    conforming_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(conforming_repo)
    result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output


@requires_just
def test_16_2_1_fails_when_the_ci_workflow_file_is_missing(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    (conforming_repo / ".github" / "workflows" / "ci.yml").unlink()
    result = invoke_lint()
    assert result.exit_code == 1
    assert "no .github/workflows/ci.yml" in result.output


@requires_just
def test_16_2_2_fails_on_trailing_whitespace_in_the_justfile(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    (conforming_repo / "justfile").write_text(JUSTFILE_WITH_TRAILING_WS)
    result = invoke_lint()
    assert result.exit_code == 1
    assert "whitespace" in result.output.lower()


@requires_just
def test_16_3_1_strips_trailing_whitespace_in_place_so_the_rerun_then_passes(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    justfile = conforming_repo / "justfile"
    justfile.write_text(JUSTFILE_WITH_TRAILING_WS)

    fix_result = invoke_lint("--fix")

    assert fix_result.exit_code == 0, fix_result.output
    assert all(line == line.rstrip(" \t") for line in justfile.read_text().split("\n"))
    assert invoke_lint().exit_code == 0


def test_16_4_1_runs_only_the_checks_named_on_the_command_line(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    (conforming_repo / ".github" / "workflows" / "ci.yml").unlink()
    result = invoke_lint("--check", "codeowners")
    assert result.exit_code == 0, result.output


def test_16_4_2_rejects_an_unknown_check_name_given_on_the_command_line(invoke_lint: Callable[..., Result]) -> None:
    result = invoke_lint("--check", "no-such-check")
    assert result.exit_code == USAGE_ERROR_EXIT
    assert "unknown bite" in result.output.lower()
    assert "no-such-check" in result.output


@requires_just
def test_16_5_1_uses_the_recipe_requirements_from_the_given_config_file_instead_of_the_bundled_defaults(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    baseline = invoke_lint("--check", "justfile")
    assert baseline.exit_code == 0, baseline.output

    config_path = conforming_repo / "cerberus.toml"
    config_path.write_text('default_recipe_marker = "just --menu"\n')
    result = invoke_lint("--check", "justfile", "--config", str(config_path))

    assert result.exit_code == 1
    assert "`default` recipe should run `just --menu`" in result.output


def test_16_6_1_skips_a_disabled_check_and_explains_why_in_the_output(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    (conforming_repo / ".github" / "CODEOWNERS").unlink()
    (conforming_repo / "pyproject.toml").write_text('[tool.cerberus]\ndisable = ["codeowners"]\n')

    result = invoke_lint("--check", "codeowners")

    assert result.exit_code == 0, result.output
    assert "codeowners" in result.output
    assert "disabled" in result.output.lower()
    assert "[tool.cerberus]" in result.output


def test_16_6_2_warns_and_carries_on_when_a_pyproject_disable_list_names_an_unknown_check(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    (conforming_repo / "pyproject.toml").write_text('[tool.cerberus]\ndisable = ["no-such-check"]\n')
    result = invoke_lint("--check", "codeowners")
    assert result.exit_code == 0, result.output
    assert "unknown disabled bites ignored: no-such-check" in result.output


def test_16_6_3_rejects_a_disable_value_that_is_not_a_list_of_check_ids(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    (conforming_repo / "pyproject.toml").write_text('[tool.cerberus]\ndisable = "codeowners"\n')
    result = invoke_lint("--check", "codeowners")
    assert isinstance(result.exception, TypeError)
    assert "list of bite id strings" in str(result.exception)


def test_16_7_1_lists_every_registered_check_by_id(known_check_ids: tuple[str, ...]) -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    assert all(check_id in result.output for check_id in known_check_ids)


def test_16_8_1_prints_the_cerberus_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == __version__


@pytest.mark.parametrize("flag", ["--json", "--strict"])
def test_16_9_1_rejects_an_option_the_lint_command_never_defined(invoke_lint: Callable[..., Result], flag: str) -> None:
    result = invoke_lint(flag)
    assert result.exit_code == USAGE_ERROR_EXIT
    assert flag.removeprefix("--") in result.output.lower()


def test_16_10_1_reports_a_crashing_check_as_an_error_instead_of_aborting_the_run(
    invoke_lint: Callable[..., Result], register_fake_check: RegisterFakeCheck
) -> None:
    def explode(_repo: Repo, _ctx: Context) -> CheckResult:
        msg = "boom"
        raise RuntimeError(msg)

    register_fake_check("codeowners", explode)

    result = invoke_lint("--check", "codeowners")

    assert result.exit_code == 1
    assert "codeowners: bite crashed: boom" in result.output
