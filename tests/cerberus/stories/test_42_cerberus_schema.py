from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from cerberus.cli import app
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

    from seam_fixtures import RunCheckWithFiles


@pytest.mark.parametrize(
    "overlay",
    [
        None,
        "",
        "[jscpd]\nthreshold = 0\n",
        '[justfile]\nrequired = [{recipe = "lint", alias = "l"}]\n',
        '[ci_check_sequence.required]\npython = ["pytest"]\n',
        '[source_oracle.types.prod]\nroots = ["services/*"]\n',
        '[knip.allowed_customizations]\nignoreBinaries = ["uv"]\n',
        '[fallow.rules]\ncomplexity-crap = "warn"\n',
    ],
)
def test_42_1_1_accepts_partial_overrides_and_missing_configuration(
    run_check_with_files: RunCheckWithFiles, overlay: str | None
) -> None:
    files: dict[str, str] = {} if overlay is None else {"cerberus.toml": overlay}
    assert not run_check_with_files("cerberus_schema", files).problems


@pytest.mark.parametrize(
    ("overlay", "location"),
    [
        ("[unknown]\noff = true", "unknown"),
        ("[vitest]\nmin_coverage = 95", "vitest.min_coverage"),
        ("jscpd = 0.5", "jscpd"),
        ('[line_length]\nwidth = "120"', "line_length.width"),
        ("[pytest]\noff = 1", "pytest.off"),
        ("[pytest]\nmin_coverage = true", "pytest.min_coverage"),
        ('[justfile]\nrequired = [{alias = "l"}]', "justfile.required.0.recipe"),
        ('[justfile]\nrequired = [{recipe = "lint", unknown = true}]', "justfile.required.0.unknown"),
        ("[ci_check_sequence.required]\npython = [123]", "ci_check_sequence.required.python.0"),
        ('[source_oracle]\ndefault_type = "unknown"', "source_oracle.default_type"),
        ('[source_oracle.types.unknown]\nroots = ["tools/*"]', "source_oracle.types.unknown"),
        ("[source_oracle.types.prod]\nneeds_tests = false", "source_oracle.types.prod.needs_tests"),
        ('[fallow.rules]\ncomplexity-crap = "invalid"', "fallow.rules.complexity-crap"),
        ('[knip.allowed_customizations]\nignoreBinaries = "uv"', "knip.allowed_customizations.ignoreBinaries"),
    ],
)
def test_42_1_2_reports_unknown_settings_and_invalid_types(
    run_check_with_files: RunCheckWithFiles, overlay: str, location: str
) -> None:
    result = run_check_with_files("cerberus_schema", {"cerberus.toml": overlay})
    assert result.problems
    assert all(f"cerberus.toml: {location}:" in finding.message for finding in result.problems)


def test_42_1_3_reports_every_schema_problem(run_check_with_files: RunCheckWithFiles) -> None:
    result = run_check_with_files("cerberus_schema", {"cerberus.toml": '[pytest]\noff = "yes"\nunknown = true'})
    assert {finding.message for finding in result.problems} == {
        "cerberus.toml: pytest.off: Input should be a valid boolean",
        "cerberus.toml: pytest.unknown: Extra inputs are not permitted",
    }


def test_42_1_4_reports_malformed_toml(run_check_with_files: RunCheckWithFiles) -> None:
    result = run_check_with_files("cerberus_schema", {"cerberus.toml": "[pytest"})
    assert len(result.problems) == 1
    assert "cerberus.toml:" in result.problems[0].message


@pytest.mark.parametrize("flags", [[], ["--check", "codeowners_coverage"], ["--fix"]])
def test_42_2_1_stops_before_loading_invalid_overrides_without_rewriting_them(tmp_path: Path, flags: list[str]) -> None:
    path = tmp_path / "cerberus.toml"
    overlay = '[pytest]\nmin_coverage = "ninety"\n'
    path.write_text(overlay)
    result = CliRunner().invoke(app, [str(tmp_path), *flags])
    assert result.exit_code == 1
    assert "error: 💢 cerberus_schema:" in result.output
    assert "pytest.min_coverage" in result.output
    assert "codeowners_coverage" not in result.output
    assert path.read_text() == overlay


@pytest.mark.parametrize("overlay", ["[cerberus_schema]\noff = true", "[cerberus_schema]"])
def test_42_2_2_has_no_configuration_table_or_disable_switch(tmp_path: Path, overlay: str) -> None:
    (tmp_path / "cerberus.toml").write_text(overlay)
    result = CliRunner().invoke(app, [str(tmp_path), "--check", "cerberus_schema"])
    assert result.exit_code == 1
    assert "cerberus_schema: Extra inputs are not permitted" in " ".join(result.output.split())


def test_42_2_3_validates_the_explicit_configuration_instead_of_the_repository_file(tmp_path: Path) -> None:
    (tmp_path / "cerberus.toml").write_text("[unknown]")
    override = tmp_path / "override.toml"
    override.write_text("[jscpd]\nthreshold = 0\n")
    result = CliRunner().invoke(app, [str(tmp_path), "--config", str(override), "--check", "cerberus_schema"])
    assert result.exit_code == 0, result.output
    assert result.output.count("🐾 cerberus_schema") == 1


def test_42_2_4_reports_an_unreadable_explicit_configuration(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, [str(tmp_path), "--config", str(tmp_path / "missing.toml"), "--check", "cerberus_schema"]
    )
    assert result.exit_code == 1
    assert "error: 💢 cerberus_schema:" in result.output
    assert str(tmp_path / "missing.toml") in result.output.replace("\n", "")
