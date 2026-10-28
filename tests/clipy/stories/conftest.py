from __future__ import annotations

import pytest
from report_fixtures import metrics_encoding, release_preparation, report_repo, unchanged_versions
from typer.testing import CliRunner


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


__all__ = ["cli", "metrics_encoding", "release_preparation", "report_repo", "unchanged_versions"]
