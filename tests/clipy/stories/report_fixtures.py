from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from clipy import code_metrics
from clipy.cli import app
from tiktoken import Encoding
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import Result


@dataclass
class ReportRepo:
    root: Path

    def write(self, path: str, content: str) -> Path:
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
        return destination

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.root, check=True, text=True, capture_output=True).stdout

    def stage(self) -> None:
        self.git("add", "--all")

    @staticmethod
    def invoke(*args: str) -> Result:
        return CliRunner().invoke(app, list(args))

    def read(self, path: str) -> str:
        return (self.root / path).read_text()


@pytest.fixture
def report_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReportRepo:
    repo = ReportRepo(tmp_path)
    repo.git("init", "-q")
    monkeypatch.chdir(tmp_path)

    return repo


@pytest.fixture
def metrics_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    encoding = Encoding(
        name="fixture",
        pat_str=r"(?s).",
        mergeable_ranks={bytes([byte]): byte for byte in range(256)},
        special_tokens={},
    )
    monkeypatch.setattr(code_metrics, "load_encoding", lambda: encoding)


def read_row(report: str, heading: str, label: str) -> dict[str, str]:
    section = report.split(f"## {heading}\n")[1].split("\n## ", maxsplit=1)[0]
    rows = [
        [cell.strip() for cell in line.split("|")[1:-1]]
        for line in section.splitlines()
        if line.startswith("|") and "---" not in line
    ]
    for cells in rows[1:]:
        if cells[0] == label:
            return dict(zip(rows[0][1:], cells[1:], strict=True))
    message = f"no row {label!r} under {heading!r}"
    raise AssertionError(message)
