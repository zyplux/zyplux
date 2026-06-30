from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest
from cerberus.checks.rumdl_config_check import CANONICAL as RUMDL_CANONICAL
from cerberus.cli import app
from cerberus.config import repo_disabled_checks
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

USAGE_ERROR_EXIT = 2  # click/typer exit code for an unknown option or bad usage

requires_just = pytest.mark.skipif(shutil.which("just") is None, reason="requires the `just` binary on PATH")

CONFORMING_JUSTFILE = """\
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
    echo install

knip:
    echo knip

typecheck:
    echo typecheck

lint:
    echo lint

test:
    echo test

check: install knip typecheck lint test

upgrade:
    echo upgrade

upgrade-interactive:
    echo upgrade-interactive

clean:
    echo clean
"""

JUSTFILE_WITH_TRAILING_WS = CONFORMING_JUSTFILE.replace(
    "check: install knip typecheck lint test\n",
    "check: install knip typecheck lint test   \n",
)

JUSTFILE_WITH_BARE_TOOL = CONFORMING_JUSTFILE.replace("lint:\n    echo lint\n", "lint:\n    rumdl check\n")

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


def _make_conforming_repo(root: Path) -> Path:
    (root / "justfile").write_text(CONFORMING_JUSTFILE)
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(CONFORMING_CI)
    (root / ".github" / "CODEOWNERS").write_text(CONFORMING_CODEOWNERS)
    (root / ".rumdl.toml").write_text(RUMDL_CANONICAL)
    return root


@requires_just
def test_lint_passes_on_conforming_checkout(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 0, result.output


@requires_just
def test_lint_fails_when_ci_workflow_missing(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    (tmp_path / ".github" / "workflows" / "ci.yml").unlink()
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 1
    assert "ci" in result.output.lower()


@requires_just
def test_lint_defaults_to_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_conforming_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output


@requires_just
def test_lint_fails_on_trailing_whitespace(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    (tmp_path / "justfile").write_text(JUSTFILE_WITH_TRAILING_WS)
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 1
    assert "whitespace" in result.output.lower()


@requires_just
def test_fix_strips_trailing_whitespace(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    justfile = tmp_path / "justfile"
    justfile.write_text(JUSTFILE_WITH_TRAILING_WS)
    result = runner.invoke(app, [str(tmp_path), "--fix"])
    assert result.exit_code == 0, result.output
    fixed = justfile.read_text()
    assert all(line == line.rstrip(" \t") for line in fixed.split("\n"))


@requires_just
def test_lint_disable_skips_a_check_via_pyproject(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    (tmp_path / ".github" / "CODEOWNERS").unlink()
    assert runner.invoke(app, [str(tmp_path), "--check", "codeowners"]).exit_code == 1

    (tmp_path / "pyproject.toml").write_text('[tool.cerberus]\ndisable = ["codeowners"]\n')
    result = runner.invoke(app, [str(tmp_path), "--check", "codeowners"])
    assert result.exit_code == 0, result.output
    assert "codeowners" in result.output
    assert "disabled" in result.output.lower()
    assert "[tool.cerberus]" in result.output


@requires_just
def test_lint_disable_ignores_unknown_check(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[tool.cerberus]\ndisable = ["no-such-check"]\n')
    result = runner.invoke(app, [str(tmp_path), "--check", "codeowners"])
    assert result.exit_code == 0, result.output


def test_repo_disabled_checks_rejects_non_list_disable(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.cerberus]\ndisable = "codeowners"\n')
    with pytest.raises(TypeError, match="list of check id strings"):
        repo_disabled_checks(tmp_path)


@requires_just
def test_lint_fails_on_bare_managed_tool(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    (tmp_path / "justfile").write_text(JUSTFILE_WITH_BARE_TOOL)
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 1
    assert "rumdl" in result.output.lower()


def test_lint_has_no_json_flag(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    result = runner.invoke(app, [str(tmp_path), "--json"])
    assert result.exit_code == USAGE_ERROR_EXIT
    assert "json" in result.output.lower()


def test_list_command_lists_every_check() -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    for check_id in (
        "justfile",
        "ci-workflow",
        "cerberus-step",
        "workflow-tooling",
        "rumdl-config",
        "codeowners",
    ):
        assert check_id in result.output


def test_lint_has_no_strict_flag(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    result = runner.invoke(app, [str(tmp_path), "--strict"])
    assert result.exit_code == USAGE_ERROR_EXIT
    assert "strict" in result.output.lower()
