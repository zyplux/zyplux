from __future__ import annotations

import pytest
from report_fixtures import metrics_encoding, report_repo
from typer.testing import CliRunner


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


__all__ = ["cli", "metrics_encoding", "report_repo"]
