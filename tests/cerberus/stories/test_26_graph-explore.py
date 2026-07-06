from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from cerberus.cli import app
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import Result

runner = CliRunner()

_PY_A = """\
from __future__ import annotations

from pkg.b import helper


def top_level_func() -> str:
    return helper()


class Widget:
    pass
"""

_PY_B = """\
from __future__ import annotations


def helper() -> str:
    return "hi"
"""


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(_PY_A)
    (tmp_path / "pkg" / "b.py").write_text(_PY_B)
    return tmp_path


def _invoke(*args: str) -> Result:
    return runner.invoke(app, list(args))


@pytest.fixture
def built_graph_path(fixture_repo: Path) -> Path:
    result = _invoke("graph", str(fixture_repo))
    assert result.exit_code == 0, result.output
    return fixture_repo / "graph.json"


def test_26_1_1_explains_a_node_found_by_its_exact_id(built_graph_path: Path) -> None:
    result = _invoke("graph-explain", "pkg_a", "--graph", str(built_graph_path))
    assert result.exit_code == 0, result.output
    assert "Node: pkg/a.py" in result.output
    assert "ID:        pkg_a" in result.output
    assert "Type:      code" in result.output


def test_26_1_2_explains_a_node_found_by_a_path_or_label_match(built_graph_path: Path) -> None:
    result = _invoke("graph-explain", "pkg/a.py", "--graph", str(built_graph_path))
    assert result.exit_code == 0, result.output
    assert "ID:        pkg_a" in result.output


def test_26_1_3_lists_a_nodes_neighbors_with_relation_and_confidence(built_graph_path: Path) -> None:
    result = _invoke("graph-explain", "pkg_a", "--graph", str(built_graph_path))
    assert result.exit_code == 0, result.output
    assert "[imports] [EXTRACTED]" in result.output
    assert "[contains] [EXTRACTED]" in result.output


def test_26_1_4_reports_no_match_for_an_unknown_node(built_graph_path: Path) -> None:
    result = _invoke("graph-explain", "zzz_nonexistent_qqq", "--graph", str(built_graph_path))
    assert result.exit_code == 0, result.output
    assert "No node matching" in result.output


def test_26_1_5_prefers_the_file_node_over_a_same_file_symbol_when_the_query_is_an_exact_path(
    built_graph_path: Path,
) -> None:
    result = _invoke("graph-explain", "pkg/a.py", "--graph", str(built_graph_path))
    assert result.exit_code == 0, result.output
    assert "Node: pkg/a.py" in result.output
    assert "ID:        pkg_a\n" in result.output


def test_26_1_6_marks_each_connections_direction_with_an_arrow(built_graph_path: Path) -> None:
    outgoing = _invoke("graph-explain", "pkg_a", "--graph", str(built_graph_path))
    assert outgoing.exit_code == 0, outgoing.output
    assert "--> pkg/b.py [imports] [EXTRACTED]" in outgoing.output
    assert "--> top_level_func [contains] [EXTRACTED]" in outgoing.output

    incoming = _invoke("graph-explain", "pkg_b", "--graph", str(built_graph_path))
    assert incoming.exit_code == 0, incoming.output
    assert "<-- pkg/a.py [imports] [EXTRACTED]" in incoming.output


@pytest.fixture
def busy_hub_repo(tmp_path: Path) -> Path:
    (tmp_path / "hub.py").write_text('def shared() -> str:\n    return "x"\n')
    for i in range(25):
        (tmp_path / f"importer_{i}.py").write_text(
            f"from hub import shared\n\n\ndef use_{i}() -> str:\n    return shared()\n"
        )
    return tmp_path


def test_26_1_7_announces_how_many_connections_were_truncated(busy_hub_repo: Path) -> None:
    built = _invoke("graph", str(busy_hub_repo))
    assert built.exit_code == 0, built.output

    result = _invoke("graph-explain", "hub", "--graph", str(busy_hub_repo / "graph.json"))
    assert result.exit_code == 0, result.output
    assert "... and " in result.output
    assert "more" in result.output


def test_26_2_1_seeds_a_traversal_from_the_best_scoring_nodes(built_graph_path: Path) -> None:
    result = _invoke("graph-query", "top_level_func", "--graph", str(built_graph_path))
    assert result.exit_code == 0, result.output
    assert "Traversal: BFS depth=2" in result.output
    assert "pkg/a.py" in result.output
    assert "pkg/b.py" in result.output


def test_26_2_2_supports_a_dfs_traversal_via_the_dfs_option(built_graph_path: Path) -> None:
    result = _invoke("graph-query", "pkg_a", "--graph", str(built_graph_path), "--dfs")
    assert result.exit_code == 0, result.output
    assert "Traversal: DFS depth=2" in result.output


def test_26_2_3_truncates_output_to_the_requested_character_budget(built_graph_path: Path) -> None:
    full = _invoke("graph-query", "pkg_a", "--graph", str(built_graph_path))
    truncated = _invoke("graph-query", "pkg_a", "--graph", str(built_graph_path), "--budget", "60")
    assert full.exit_code == 0, full.output
    assert truncated.exit_code == 0, truncated.output
    assert len(truncated.output) < len(full.output)


def test_26_3_1_fails_with_a_clear_error_when_graph_json_does_not_exist(tmp_path: Path) -> None:
    missing = tmp_path / "nope" / "graph.json"
    result = _invoke("graph-explain", "anything", "--graph", str(missing))
    assert result.exit_code != 0
    assert "graph file not found" in result.output
