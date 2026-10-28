from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from repository_fixture import read_row

if TYPE_CHECKING:
    from repository_fixture import ReleasePreparation, ReportRepo

pytestmark = pytest.mark.usefixtures("metrics_encoding")

TARGET = 'scope = "@fixture"\n[app]\nkind = "npm"\n[app.version]\nfile = "package.json"\njson = "version"\n'


def test_39_1_1_prepares_releases_then_generates_the_graph_before_measuring_it(
    report_repo: ReportRepo, release_preparation: ReleasePreparation
) -> None:
    report_repo.write_package("", name="fixture", version="1.0.0")
    report_repo.write("airlock-targets.toml", TARGET)
    report_repo.write("WORKSPACE_GRAPH.md", "# Previous graph\n")
    report_repo.stage()
    index = report_repo.git("ls-files", "--stage")
    result = report_repo.invoke("fingerprint")
    assert result.exit_code == 0, result.output
    assert release_preparation.calls == [report_repo.root]
    assert '"1.0.1"' in report_repo.read("package.json")
    graph = report_repo.read("WORKSPACE_GRAPH.md")
    assert "flowchart LR" in graph
    report = report_repo.read("line_and_token_stats.md")
    assert read_row(report, "Line Counts", "Markdown")["Total"] == str(
        sum(bool(line.strip()) for line in graph.splitlines())
    )
    assert report_repo.git("ls-files", "--stage") == index


@pytest.mark.parametrize("manifest", [None, 'scope = "@fixture"\n'])
def test_39_1_2_skips_release_preparation_without_targets(
    report_repo: ReportRepo, release_preparation: ReleasePreparation, manifest: str | None
) -> None:
    report_repo.write("readme.md", "# Repository\n")
    if manifest is not None:
        report_repo.write("airlock-targets.toml", manifest)
    report_repo.stage()
    result = report_repo.invoke("fingerprint")
    assert result.exit_code == 0, result.output
    assert not release_preparation.calls
    assert "No release targets" in result.output
    assert (report_repo.root / "WORKSPACE_GRAPH.md").is_file()
    assert (report_repo.root / "line_and_token_stats.md").is_file()


def test_39_1_3_resolves_explicit_and_nested_paths_to_the_repository_root(
    report_repo: ReportRepo, release_preparation: ReleasePreparation, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_repo.write_package("", name="fixture", version="1.0.0")
    report_repo.write("airlock-targets.toml", TARGET)
    nested = report_repo.write("docs/readme.md", "# Documentation\n").parent
    report_repo.stage()
    monkeypatch.chdir(report_repo.root.parent)
    result = report_repo.invoke("fingerprint", str(nested))
    assert result.exit_code == 0, result.output
    assert release_preparation.calls == [report_repo.root]
    assert not (nested / "WORKSPACE_GRAPH.md").exists()
    assert not (nested / "line_and_token_stats.md").exists()


def test_39_2_1_stops_before_generating_reports_when_preparation_fails(
    report_repo: ReportRepo, release_preparation: ReleasePreparation
) -> None:
    report_repo.write_package("", name="fixture", version="1.0.0")
    report_repo.write("airlock-targets.toml", TARGET)
    report_repo.stage()
    release_preparation.should_fail = True
    result = report_repo.invoke("fingerprint")
    assert result.exit_code == 1
    assert "release preparation failed" in result.output
    assert not (report_repo.root / "WORKSPACE_GRAPH.md").exists()
    assert not (report_repo.root / "line_and_token_stats.md").exists()


def test_39_2_2_reports_invalid_targets_before_starting_preparation(
    report_repo: ReportRepo, release_preparation: ReleasePreparation
) -> None:
    report_repo.write("airlock-targets.toml", "broken = [")
    result = report_repo.invoke("fingerprint")
    assert result.exit_code == 1
    assert not release_preparation.calls
    assert not (report_repo.root / "WORKSPACE_GRAPH.md").exists()
