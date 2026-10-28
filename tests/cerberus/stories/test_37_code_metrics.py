from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from repository_fixture import read_row

if TYPE_CHECKING:
    from pathlib import Path

    from repository_fixture import ReportRepo

pytestmark = pytest.mark.usefixtures("metrics_encoding")

TS_SOURCE = "// tally the total\nconst total = 1 + 2;\n\nconst label = total > 2 ? 'big' : 'small';\n"


def test_37_1_1_splits_typescript_into_prose_code_and_branches(report_repo: ReportRepo) -> None:
    report_repo.write("tally.ts", TS_SOURCE)
    report_repo.stage()
    result = report_repo.invoke("stats")
    assert result.exit_code == 0, result.output
    report = report_repo.read("line_and_token_stats.md")
    assert read_row(report, "Line Counts", ".ts") == {
        "Files": "1",
        "Prose": "33.3%",
        "Code": "66.7%",
        "Branch": "33.3%",
        "Total": "3",
    }
    assert int(read_row(report, "Lexical Token and CST Node Counts", ".ts")["CST"]) > 0
    assert int(read_row(report, "BPE Token Counts", ".ts")["Total"]) > 0


@pytest.mark.parametrize(
    ("path", "source", "language"),
    [
        ("ui.tsx", "export const ui = <p>hello</p>;\n", ".tsx"),
        ("a.mts", "export const a = true;\n", ".ts"),
        ("a.cts", "export const a = 42;\n", ".ts"),
        ("a.py", '"""Description."""\nif True:\n    print("hello")\n', "Python"),
        ("a.css", "p { color: red; }\n", "CSS"),
        ("a.html", '<p class="intro">hello</p>\n', "HTML"),
        ("a.json", '{"key": true}\n', "JSON"),
        ("a.jsonc", '// description\n{"key": 42}\n', "JSON"),
        ("a.yaml", "message: |\n  hello\n  world\n", "YAML"),
        ("a.toml", 'message = "hello"\n', "TOML"),
        ("a.nix", '{ message = "hello"; }\n', "Nix"),
        ("a.sh", 'if true; then echo "hello"; fi\n', "Shell"),
        ("a.sql", "CREATE TABLE sessions (id TEXT);\n", "SQL"),
        ("Dockerfile", '# base image\nFROM node:26\nRUN echo "hello"\n', "Dockerfile"),
    ],
)
def test_37_1_2_measures_each_supported_grammar_without_network_access(
    report_repo: ReportRepo, path: str, source: str, language: str
) -> None:
    report_repo.write(path, source)
    report_repo.stage()
    result = report_repo.invoke("stats")
    assert result.exit_code == 0, result.output
    report = report_repo.read("line_and_token_stats.md")
    assert read_row(report, "Line Counts", language)["Files"] == "1"
    assert int(read_row(report, "Lexical Token and CST Node Counts", language)["Total"]) > 0


def test_37_1_3_keeps_prose_unknown_languages_and_binaries_distinct(report_repo: ReportRepo) -> None:
    report_repo.write("readme.md", "# Title\n\nSome prose.\n")
    report_repo.write("notes.txt", "first\n\nsecond\n")
    report_repo.write("logo.png", "image\0binary")
    report_repo.stage()
    assert report_repo.invoke("stats").exit_code == 0
    report = report_repo.read("line_and_token_stats.md")
    assert read_row(report, "Line Counts", "Markdown")["Prose"] == "100.0%"
    assert read_row(report, "Line Counts", ".txt")["Code"] == "—"
    assert "- `logo.png` — binary" in report
    assert read_row(report, "Line Counts", "**Total**")["Files"] == "2"


def test_37_1_4_rolls_up_typescript_without_counting_it_twice(report_repo: ReportRepo) -> None:
    report_repo.write("a.ts", TS_SOURCE)
    report_repo.write("ui.tsx", "export const ui = <p>hello</p>;\n")
    report_repo.stage()
    assert report_repo.invoke("stats").exit_code == 0
    report = report_repo.read("line_and_token_stats.md")
    assert read_row(report, "Line Counts", "TypeScript")["Total"] == "4"
    assert read_row(report, "Line Counts", "**Total**")["Files"] == "2"


def test_37_2_1_reads_tracked_worktree_content_without_changing_the_index(report_repo: ReportRepo) -> None:
    report_repo.write("readme.md", "# Original\n")
    report_repo.stage()
    before = report_repo.git("ls-files", "--stage")
    report_repo.write("readme.md", "# Current\n\nChanged prose.\n")
    report_repo.write("untracked.ts", TS_SOURCE)
    assert report_repo.invoke("stats").exit_code == 0
    assert read_row(report_repo.read("line_and_token_stats.md"), "Line Counts", "**Total**")["Files"] == "1"
    assert read_row(report_repo.read("line_and_token_stats.md"), "Line Counts", "Markdown")["Total"] == "2"
    assert report_repo.git("ls-files", "--stage") == before


def test_37_2_2_excludes_lockfiles_deleted_files_and_custom_report_destinations(report_repo: ReportRepo) -> None:
    report_repo.write("readme.md", "# Title\n")
    report_repo.write("pnpm-lock.yaml", "lockfileVersion: 9\n")
    report_repo.write("uv.lock", "version = 1\n")
    report_repo.write("report.md", "# Previous report\n")
    removed = report_repo.write("deleted.ts", TS_SOURCE)
    report_repo.stage()
    removed.unlink()
    assert report_repo.invoke("stats", "--out", "report.md").exit_code == 0
    assert read_row(report_repo.read("report.md"), "Line Counts", "**Total**")["Files"] == "1"


def test_37_2_3_uses_shared_production_ownership_in_scoped_reports(report_repo: ReportRepo) -> None:
    report_repo.write("cerberus.toml", '[source]\nproduction_roots = ["services/*"]\ndemo_roots = ["services/demo"]\n')
    report_repo.write("services/api/server.ts", TS_SOURCE)
    report_repo.write("services/api/server.test.ts", TS_SOURCE)
    report_repo.write("services/demo/server.ts", TS_SOURCE)
    report_repo.stage()
    result = report_repo.invoke("stats", "services", "--title", "service corpus", "-o", "reports/services.md")
    assert result.exit_code == 0, result.output
    report = report_repo.read("reports/services.md")
    assert report.startswith("# Stats - service corpus\n")
    assert read_row(report, "Line Counts", ".ts")["Files"] == "3"
    assert read_row(report, "Production Line Counts", ".ts")["Files"] == "1"


def test_37_3_1_reports_empty_scopes_and_missing_repositories(report_repo: ReportRepo, tmp_path: Path) -> None:
    empty = report_repo.invoke("stats")
    assert empty.exit_code == 1
    assert "no tracked files" in empty.output
    outside = tmp_path.parent / "outside"
    outside.mkdir()
    missing = report_repo.invoke("stats", str(outside))
    assert missing.exit_code == 1
    assert "not inside a git repository" in missing.output
