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
    from seam_fixtures import RegisterFakeCheck
    from typer.testing import Result


runner = CliRunner()

USAGE_ERROR_EXIT = 2

requires_just = pytest.mark.skipif(shutil.which("just") is None, reason="requires the `just` binary on PATH")

BASELINE_JUST = resources.files("cerberus").joinpath("baseline.just").read_text()
CONFORMING_JUSTFILE = f"# BASELINE\n{BASELINE_JUST}\n# CUSTOM\n"

JUSTFILE_WITH_TRAILING_WS = CONFORMING_JUSTFILE.replace(
    "check: install knip typecheck lint test cerberus\n",
    "check: install knip typecheck lint test cerberus   \n",
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
def test_16_1_3_prints_one_line_per_active_bite_with_its_id_and_outcome(
    conforming_repo: Path, invoke_lint: Callable[..., Result], known_check_ids: tuple[str, ...], ctx: Context
) -> None:
    (conforming_repo / ".github" / "CODEOWNERS").unlink()

    result = invoke_lint()

    assert result.exit_code == 1
    for check_id in known_check_ids:
        if check_id in ctx.config.disabled_bites:
            assert check_id not in result.output
            continue
        rendered = (f"🐾 {check_id}", f"💢 {check_id}:", f"○ {check_id}:")
        assert any(line in result.output for line in rendered)
    assert "💢 codeowners_coverage:" in result.output
    assert "🐾 justfile_baseline" in result.output


def test_16_1_4_appends_a_bites_measured_detail_to_its_line(
    invoke_lint: Callable[..., Result], register_fake_check: RegisterFakeCheck, check_result: type[CheckResult]
) -> None:
    def measured(repo: Repo, _ctx: Context) -> CheckResult:
        result = check_result("codeowners_coverage", repo.name)
        result.detail = "ts: 1167 (2.20%); py: 1623 (1.30%)"
        return result

    register_fake_check("codeowners_coverage", measured)

    result = invoke_lint("--check", "codeowners_coverage")

    assert result.exit_code == 0, result.output
    assert "🐾 codeowners_coverage ts: 1167 (2.20%); py: 1623 (1.30%)" in result.output


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
    result = invoke_lint("--check", "codeowners_coverage")
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
    baseline = invoke_lint("--check", "justfile_baseline")
    assert baseline.exit_code == 0, baseline.output

    config_path = conforming_repo / "cerberus.toml"
    config_path.write_text('[justfile_baseline]\ndefault_recipe_marker = "just --menu"\n')
    result = invoke_lint("--check", "justfile_baseline", "--config", str(config_path))

    assert result.exit_code == 1
    assert "`default` recipe should run `just --menu`" in result.output


def test_16_5_2_rejects_a_config_file_whose_section_is_not_a_table(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    config_path = conforming_repo / "cerberus.toml"
    scalar_section = 'jscpd_dupes_threshold = 0.5\n\n[justfile_baseline]\ndefault_recipe_marker = "just --list"\n'
    config_path.write_text(scalar_section)

    result = invoke_lint("--check", "codeowners_coverage", "--config", str(config_path))

    assert isinstance(result.exception, TypeError)
    assert "[jscpd_dupes_threshold] must be a table" in str(result.exception)


@requires_just
def test_16_6_1_leaves_an_off_bite_out_of_the_run_and_the_output(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    (conforming_repo / ".github" / "CODEOWNERS").unlink()
    (conforming_repo / "cerberus.toml").write_text("[codeowners_coverage]\noff = true\n")

    result = invoke_lint()

    assert result.exit_code == 0, result.output
    assert "codeowners_coverage" not in result.output


def test_16_6_2_runs_an_off_bite_when_named_explicitly_with_check(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    (conforming_repo / ".github" / "CODEOWNERS").unlink()
    (conforming_repo / "cerberus.toml").write_text("[codeowners_coverage]\noff = true\n")

    result = invoke_lint("--check", "codeowners_coverage")

    assert result.exit_code == 1
    assert "💢 codeowners_coverage:" in result.output


@requires_just
def test_16_6_3_re_enables_a_bundled_off_bite_when_the_repo_overlay_sets_off_to_false(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    without_overlay = invoke_lint()
    assert "tool_pins_latest" not in without_overlay.output

    (conforming_repo / "cerberus.toml").write_text("[tool_pins_latest]\noff = false\n")
    result = invoke_lint()

    assert result.exit_code == 0, result.output
    assert "○ tool_pins_latest: no cerberus tool pins source in the repo" in result.output


def test_16_6_4_warns_and_carries_on_when_an_off_table_names_an_unknown_bite(
    conforming_repo: Path, invoke_lint: Callable[..., Result]
) -> None:
    (conforming_repo / "cerberus.toml").write_text("[no_such_bite]\noff = true\n")
    result = invoke_lint("--check", "codeowners_coverage")
    assert result.exit_code == 0, result.output
    assert "unknown off bites ignored: no_such_bite" in result.output


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

    register_fake_check("codeowners_coverage", explode)

    result = invoke_lint("--check", "codeowners_coverage")

    assert result.exit_code == 1
    assert "codeowners_coverage: bite crashed: boom" in result.output


def test_16_11_1_renders_a_skipped_bite_with_its_skip_glyph_and_reason(
    invoke_lint: Callable[..., Result], register_fake_check: RegisterFakeCheck, check_result: type[CheckResult]
) -> None:
    def skipping(repo: Repo, _ctx: Context) -> CheckResult:
        result = check_result("codeowners_coverage", repo.name)
        result.skip("no release-targets.toml — repo publishes nothing")
        return result

    register_fake_check("codeowners_coverage", skipping)

    result = invoke_lint("--check", "codeowners_coverage")

    assert result.exit_code == 0, result.output
    assert "○ codeowners_coverage: no release-targets.toml — repo publishes nothing" in result.output
    assert "🐾 codeowners_coverage" not in result.output


_REPO_OVERRIDE_TOML = "[jscpd_dupes_threshold]\nthreshold = 7\n"


def _register_config_probe(register_fake_check: RegisterFakeCheck, check_result: type[CheckResult]) -> None:
    def probe(repo: Repo, ctx: Context) -> CheckResult:
        result = check_result("codeowners_coverage", repo.name)
        result.detail = f"threshold {ctx.config.jscpd_dupes_threshold:g} marker `{ctx.config.default_recipe_marker}`"
        return result

    register_fake_check("codeowners_coverage", probe)


def test_16_12_1_overlays_a_repo_root_cerberus_toml_onto_the_bundled_defaults(
    conforming_repo: Path,
    invoke_lint: Callable[..., Result],
    register_fake_check: RegisterFakeCheck,
    check_result: type[CheckResult],
) -> None:
    _register_config_probe(register_fake_check, check_result)
    (conforming_repo / "cerberus.toml").write_text(_REPO_OVERRIDE_TOML)

    result = invoke_lint("--check", "codeowners_coverage")

    assert result.exit_code == 0, result.output
    assert "threshold 7 marker `just --list`" in result.output


def test_16_12_2_replaces_the_configuration_wholesale_when_an_explicit_config_file_is_given(
    conforming_repo: Path,
    invoke_lint: Callable[..., Result],
    register_fake_check: RegisterFakeCheck,
    check_result: type[CheckResult],
) -> None:
    _register_config_probe(register_fake_check, check_result)
    (conforming_repo / "cerberus.toml").write_text(_REPO_OVERRIDE_TOML)
    explicit = conforming_repo / "explicit.toml"
    explicit.write_text('[justfile_baseline]\ndefault_recipe_marker = "just --menu"\n')

    result = invoke_lint("--check", "codeowners_coverage", "--config", str(explicit))

    assert result.exit_code == 0, result.output
    assert "threshold 0.1 marker `just --menu`" in result.output


def test_16_13_1_prints_a_bites_verbose_lines_only_when_run_with_verbose(
    invoke_lint: Callable[..., Result], register_fake_check: RegisterFakeCheck, check_result: type[CheckResult]
) -> None:
    def measured_clones(repo: Repo, ctx: Context) -> CheckResult:
        result = check_result("codeowners_coverage", repo.name)
        result.ok("duplication is under the threshold in every language")
        if ctx.verbose:
            result.verbose_lines = ["    src/a.ts [4:1 - 24:9] duplicates src/b.ts [40:1 - 60:9]"]
        return result

    register_fake_check("codeowners_coverage", measured_clones)

    plain = invoke_lint("--check", "codeowners_coverage")
    assert plain.exit_code == 0, plain.output
    assert "duplicates" not in plain.output

    verbose = invoke_lint("--check", "codeowners_coverage", "--verbose")
    assert verbose.exit_code == 0, verbose.output
    assert "src/a.ts [4:1 - 24:9] duplicates src/b.ts [40:1 - 60:9]" in verbose.output
