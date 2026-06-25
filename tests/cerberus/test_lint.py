from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from cerberus.checks.rumdl_config_check import CANONICAL as RUMDL_CANONICAL
from cerberus.cli import app
from typer.testing import CliRunner

runner = CliRunner()

requires_just = pytest.mark.skipif(
    shutil.which("just") is None, reason="requires the `just` binary on PATH"
)

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

JUSTFILE_WITH_BARE_TOOL = CONFORMING_JUSTFILE.replace(
    "lint:\n    echo lint\n", "lint:\n    rumdl check\n"
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
def test_lint_defaults_to_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_conforming_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output


@requires_just
def test_lint_skips_control_plane_checks(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    result = runner.invoke(app, [str(tmp_path), "--check", "workflow-secrets"])
    assert result.exit_code == 0, result.output
    assert "all checks pass" in result.output.lower()


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
def test_lint_fails_on_bare_managed_tool(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    (tmp_path / "justfile").write_text(JUSTFILE_WITH_BARE_TOOL)
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 1
    assert "rumdl" in result.output.lower()


def test_lint_has_no_json_flag(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    result = runner.invoke(app, [str(tmp_path), "--json"])
    assert result.exit_code == 2
    assert "json" in result.output.lower()


def test_org_rejects_removed_subcommands() -> None:
    for removed in ("scorecard", "repos"):
        result = runner.invoke(app, ["org", "zyplux", removed])
        assert result.exit_code == 2, f"{removed}: {result.output}"


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
        "workflow-secrets",
    ):
        assert check_id in result.output


def test_org_requires_an_org_argument() -> None:
    result = runner.invoke(app, ["org"])
    assert result.exit_code == 2
    assert "ORG" in result.output or "Missing argument" in result.output


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("zyplux", "zyplux"),
        ("github.com/zyplux", "zyplux"),
        ("https://github.com/zyplux", "zyplux"),
        ("https://github.com/zyplux/", "zyplux"),
        ("git@github.com:zyplux", "zyplux"),
        ("github.com/zyplux/some-repo", "zyplux"),
    ],
)
def test_parse_org_ref_accepts_known_forms(ref: str, expected: str) -> None:
    from cerberus.source import parse_org_ref

    assert parse_org_ref(ref) == expected


@pytest.mark.parametrize("ref", ["", "  ", "gitlab.com/zyplux", "https://example.com/x"])
def test_parse_org_ref_rejects_unknown_hosts(ref: str) -> None:
    from cerberus.source import parse_org_ref

    with pytest.raises(ValueError):
        parse_org_ref(ref)


def test_lint_has_no_strict_flag(tmp_path: Path) -> None:
    _make_conforming_repo(tmp_path)
    result = runner.invoke(app, [str(tmp_path), "--strict"])
    assert result.exit_code == 2
    assert "strict" in result.output.lower()
