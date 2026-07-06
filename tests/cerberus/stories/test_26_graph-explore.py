from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx
import pytest
from cerberus.cli import app
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

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


@pytest.fixture
def mega_hub_repo(tmp_path: Path) -> Path:
    (tmp_path / "hub.py").write_text('def shared() -> str:\n    return "x"\n')
    (tmp_path / "seed_file.py").write_text("from hub import shared\n\n\ndef seed_use() -> str:\n    return shared()\n")
    for i in range(60):
        (tmp_path / f"importer_{i}.py").write_text(
            f"from hub import shared\n\n\ndef use_{i}() -> str:\n    return shared()\n"
        )
    return tmp_path


def test_26_2_4_stops_expanding_through_a_hub_node_without_excluding_the_hub_itself(
    mega_hub_repo: Path,
) -> None:
    built = _invoke("graph", str(mega_hub_repo))
    assert built.exit_code == 0, built.output

    graph_path = mega_hub_repo / "graph.json"
    result = _invoke("graph-query", "seed_file", "--graph", str(graph_path), "--budget", "100000")
    assert result.exit_code == 0, result.output
    assert "NODE hub.py [" in result.output
    assert "NODE importer_0.py [" not in result.output


@pytest.fixture
def term_starved_repo(tmp_path: Path) -> Path:
    (tmp_path / "widget_service.py").write_text('def widget_only() -> str:\n    return "w"\n')
    for i in range(3):
        (tmp_path / f"helper_{i}.py").write_text(f'def helper() -> str:\n    return "h{i}"\n')
    return tmp_path


def test_26_2_5_guarantees_a_seed_for_every_distinct_query_term(term_starved_repo: Path) -> None:
    built = _invoke("graph", str(term_starved_repo))
    assert built.exit_code == 0, built.output

    graph_path = term_starved_repo / "graph.json"
    result = _invoke("graph-query", "widget helper", "--graph", str(graph_path), "--budget", "100000")
    assert result.exit_code == 0, result.output

    header = result.output.splitlines()[0]
    assert "widget" in header


@pytest.fixture
def term_rarity_repo(tmp_path: Path) -> Path:
    for i in range(8):
        (tmp_path / f"helper_{i}.py").write_text('def helper() -> str:\n    return "h"\n')
    (tmp_path / "widgetronic_file.py").write_text('def widgetronic() -> str:\n    return "w"\n')
    return tmp_path


def test_26_2_6_scores_rarer_terms_higher_than_common_terms(term_rarity_repo: Path) -> None:
    built = _invoke("graph", str(term_rarity_repo))
    assert built.exit_code == 0, built.output

    graph_path = term_rarity_repo / "graph.json"
    result = _invoke("graph-query", "helper widgetronic", "--graph", str(graph_path), "--budget", "100000")
    assert result.exit_code == 0, result.output

    header = result.output.splitlines()[0]
    assert "Start: ['widgetronic'" in header


def test_26_3_1_fails_with_a_clear_error_when_graph_json_does_not_exist(tmp_path: Path) -> None:
    missing = tmp_path / "nope" / "graph.json"
    result = _invoke("graph-explain", "anything", "--graph", str(missing))
    assert result.exit_code != 0
    assert "graph file not found" in result.output


@pytest.fixture
def long_path_repo(tmp_path: Path) -> Path:
    nested = tmp_path / "a" / "deeply" / "nested" / "package" / "structure"
    nested.mkdir(parents=True)
    (nested / "module_with_a_long_name.py").write_text('def shared() -> str:\n    return "x"\n')
    return tmp_path


def test_26_4_1_never_wraps_a_nodes_bracketed_metadata_onto_its_own_line(long_path_repo: Path) -> None:
    built = _invoke("graph", str(long_path_repo))
    assert built.exit_code == 0, built.output

    graph_path = long_path_repo / "graph.json"
    result = _invoke("graph-query", "module_with_a_long_name", "--graph", str(graph_path), "--budget", "10000")
    assert result.exit_code == 0, result.output

    path = "a/deeply/nested/package/structure/module_with_a_long_name.py"
    assert f"NODE {path} [src={path} loc=L1 community=" in result.output


def test_26_5_1_scores_a_query_term_as_an_exact_whole_token_hit_inside_a_multi_word_label(
    graph_search: ModuleType,
) -> None:
    graph: nx.Graph[str] = nx.Graph()
    graph.add_node("multi_token_hit", label="handle_get_user_request")
    graph.add_node("single_token_control", label="authusers")

    scores = {node_id: score for score, node_id in graph_search.score_nodes(graph, "user")}

    assert scores["multi_token_hit"] > scores["single_token_control"]
