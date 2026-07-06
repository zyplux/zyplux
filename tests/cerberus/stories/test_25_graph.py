from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from cerberus.cli import app
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import Result

runner = CliRunner()

GraphData = dict[str, Any]

_ABSOLUTE_PATH_MARKER = "zz_absolute_leak_marker"
_FIXTURE_FILE_COUNT = 7
_EXTERNAL_SPECIFIERS = frozenset({"os", "zod"})

_PY_A = """\
from __future__ import annotations

import os as _os

from pkg.b import helper


def top_level_func() -> str:
    return helper() + _os.linesep


class Widget:
    pass
"""

_PY_B = """\
from __future__ import annotations

from . import a


def helper() -> str:
    return f"hi from {a.top_level_func.__name__}"
"""

_PY_C = """\
from __future__ import annotations

from .b import helper


def wraps_helper() -> str:
    return helper()
"""

_TS_FOO = """\
export function topFn(): string {
  return "foo";
}
"""

_TS_BAR = """\
import { z } from "zod";

import { topFn } from "./foo";

export function useFoo(): string {
  return topFn() + String(z);
}
"""

_UTIL_PACKAGE_JSON = json.dumps({
    "name": "@acme/util",
    "exports": {".": {"types": "./src/index.ts", "default": "./src/index.ts"}},
})

_UTIL_INDEX = """\
export function identity<T>(value: T): T {
  return value;
}
"""

_APP_MAIN = """\
import { identity } from "@acme/util";

export function run(): number {
  return identity(1);
}
"""


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / _ABSOLUTE_PATH_MARKER
    root.mkdir()
    return root


@pytest.fixture
def fixture_repo(repo_root: Path) -> Path:
    (repo_root / "pkg").mkdir(parents=True)
    (repo_root / "pkg" / "a.py").write_text(_PY_A)
    (repo_root / "pkg" / "b.py").write_text(_PY_B)
    (repo_root / "pkg" / "c.py").write_text(_PY_C)

    (repo_root / "src").mkdir()
    (repo_root / "src" / "foo.ts").write_text(_TS_FOO)
    (repo_root / "src" / "bar.ts").write_text(_TS_BAR)

    (repo_root / "packages" / "util" / "src").mkdir(parents=True)
    (repo_root / "packages" / "util" / "package.json").write_text(_UTIL_PACKAGE_JSON)
    (repo_root / "packages" / "util" / "src" / "index.ts").write_text(_UTIL_INDEX)

    (repo_root / "apps" / "app" / "src").mkdir(parents=True)
    (repo_root / "apps" / "app" / "src" / "main.ts").write_text(_APP_MAIN)

    return repo_root


def _invoke(repo: Path, *args: str) -> Result:
    return runner.invoke(app, ["graph", str(repo), *args])


def _load_graph(repo: Path) -> GraphData:
    return json.loads((repo / "graph.json").read_text())


@pytest.fixture
def built_graph(fixture_repo: Path) -> GraphData:
    result = _invoke(fixture_repo)
    assert result.exit_code == 0, result.output
    return _load_graph(fixture_repo)


def _has_edge(data: GraphData, source: str, target: str, relation: str) -> bool:
    return any(e["source"] == source and e["target"] == target and e["relation"] == relation for e in data["edges"])


def _node_ids(data: GraphData) -> set[str]:
    return {node["id"] for node in data["nodes"]}


def test_25_1_1_connects_two_python_files_that_import_each_other(built_graph: GraphData) -> None:
    assert _has_edge(built_graph, "pkg_a", "pkg_b", "imports")
    assert _has_edge(built_graph, "pkg_b", "pkg_a", "imports")


def test_25_1_2_connects_a_typescript_file_to_the_file_it_imports_via_a_relative_path(
    built_graph: GraphData,
) -> None:
    assert _has_edge(built_graph, "src_bar", "src_foo", "imports")


def test_25_1_3_resolves_a_workspace_package_alias_import_to_its_entry_file(built_graph: GraphData) -> None:
    assert _has_edge(built_graph, "apps_app_src_main", "packages_util_src_index", "imports")


def test_25_1_4_resolves_a_relative_import_that_names_a_sibling_submodule(built_graph: GraphData) -> None:
    assert _has_edge(built_graph, "pkg_c", "pkg_b", "imports")


def test_25_2_1_adds_a_contained_symbol_node_for_each_top_level_function_and_class(built_graph: GraphData) -> None:
    node_ids = _node_ids(built_graph)
    assert "pkg_a__top_level_func" in node_ids
    assert "pkg_a__widget" in node_ids
    assert _has_edge(built_graph, "pkg_a", "pkg_a__top_level_func", "contains")
    assert _has_edge(built_graph, "pkg_a", "pkg_a__widget", "contains")

    function_node = next(n for n in built_graph["nodes"] if n["id"] == "pkg_a__top_level_func")
    class_node = next(n for n in built_graph["nodes"] if n["id"] == "pkg_a__widget")
    assert function_node["kind"] == "function"
    assert class_node["kind"] == "class"


def test_25_3_1_adds_no_node_or_edge_for_a_third_party_or_standard_library_import(built_graph: GraphData) -> None:
    file_nodes = [n for n in built_graph["nodes"] if n["kind"] == "file"]
    assert len(file_nodes) == _FIXTURE_FILE_COUNT
    node_ids = _node_ids(built_graph)
    assert node_ids.isdisjoint(_EXTERNAL_SPECIFIERS)
    edge_endpoints = {e["source"] for e in built_graph["edges"]} | {e["target"] for e in built_graph["edges"]}
    assert edge_endpoints <= node_ids


def test_25_4_1_writes_graph_json_to_the_repo_root_by_default(fixture_repo: Path) -> None:
    result = _invoke(fixture_repo)
    assert result.exit_code == 0, result.output
    assert (fixture_repo / "graph.json").is_file()


def test_25_4_2_writes_output_under_the_directory_given_via_the_out_option(fixture_repo: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "custom-out"
    result = _invoke(fixture_repo, "--out", str(out_dir))
    assert result.exit_code == 0, result.output
    assert (out_dir / "graph.json").is_file()
    assert not (fixture_repo / "graph.json").exists()


def test_25_5_1_keeps_every_node_id_free_of_the_absolute_checkout_path(fixture_repo: Path) -> None:
    result = _invoke(fixture_repo)
    assert result.exit_code == 0, result.output
    data = _load_graph(fixture_repo)

    assert _ABSOLUTE_PATH_MARKER not in json.dumps([node["id"] for node in data["nodes"]])
    for node in data["nodes"]:
        assert str(fixture_repo) not in node["id"]
        assert _ABSOLUTE_PATH_MARKER not in node["id"]


def test_25_6_1_stamps_each_node_with_graphifys_source_type_and_community_fields(built_graph: GraphData) -> None:
    file_node = next(n for n in built_graph["nodes"] if n["id"] == "pkg_a")
    assert file_node["source_file"] == "pkg/a.py"
    assert file_node["file_type"] == "code"
    assert file_node["source_location"] == "L1"

    function_node = next(n for n in built_graph["nodes"] if n["id"] == "pkg_a__top_level_func")
    assert function_node["source_location"] == "L8"

    class_node = next(n for n in built_graph["nodes"] if n["id"] == "pkg_a__widget")
    assert class_node["source_location"] == "L12"

    communities = built_graph["communities"]
    for node in built_graph["nodes"]:
        assert isinstance(node["community"], int)
        assert node["id"] in communities[node["community"]]


def test_25_6_2_marks_every_contains_edge_as_confidently_extracted(built_graph: GraphData) -> None:
    contains_edges = [e for e in built_graph["edges"] if e["relation"] == "contains"]
    assert contains_edges
    assert all(e["confidence"] == "EXTRACTED" for e in contains_edges)
