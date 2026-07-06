from __future__ import annotations

from typing import TYPE_CHECKING, cast

import networkx as nx

from cerberus.graph import ids, parse, resolve_python, resolve_ts
from cerberus.graph.model import Edge, GraphResult, Node

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

_GOD_NODE_LIMIT = 10
_TS_SUFFIXES = (".ts", ".tsx")


def _is_source(path: str) -> bool:
    return path.endswith(".py") or path.endswith(_TS_SUFFIXES)


def _resolve_targets(
    path: str,
    extracted: parse.Extracted,
    known_files: frozenset[str],
    package_index: dict[str, resolve_ts.PackageInfo],
) -> list[str]:
    if path.endswith(".py"):
        targets = (resolve_python.resolve(path, ref, known_files) for ref in extracted.py_imports)
    else:
        targets = (
            resolve_ts.resolve(path, specifier, known_files, package_index) for specifier in extracted.ts_specifiers
        )
    return [target for target in targets if target is not None]


def _add_file_and_symbols(path: str, extracted: parse.Extracted, nodes: dict[str, Node], edges: list[Edge]) -> None:
    owner_id = ids.file_id(path)
    nodes[owner_id] = Node(owner_id, "file", path, path, line=1)
    for symbol in extracted.symbols:
        node_id = ids.symbol_id(owner_id, symbol.name)
        nodes[node_id] = Node(node_id, symbol.kind, symbol.name, path, line=symbol.line)
        edges.append(Edge(owner_id, node_id, "contains"))


def build(repo: Repo, ctx: Context) -> GraphResult:
    all_paths = ctx.paths(repo)
    source_paths = sorted(path for path in all_paths if _is_source(path))
    contents = {path: content for path in source_paths if (content := ctx.file(repo, path)) is not None}
    known_files = frozenset(contents)
    package_index = resolve_ts.build_package_index(all_paths, lambda path: ctx.file(repo, path))
    extracted_by_path = {path: parse.extract(path, content) for path, content in contents.items()}

    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    for path, extracted in extracted_by_path.items():
        _add_file_and_symbols(path, extracted, nodes, edges)

    for path, extracted in extracted_by_path.items():
        owner_id = ids.file_id(path)
        targets = _resolve_targets(path, extracted, known_files, package_index)
        edges.extend(Edge(owner_id, ids.file_id(target), "imports", "EXTRACTED") for target in targets)

    graph = _to_networkx(nodes, edges)
    return GraphResult(
        nodes=list(nodes.values()),
        edges=edges,
        communities=_communities(graph),
        god_nodes=_god_nodes(graph),
    )


def _to_networkx(nodes: dict[str, Node], edges: list[Edge]) -> nx.Graph[str]:
    graph: nx.Graph[str] = nx.Graph()
    for node_id, node in nodes.items():
        graph.add_node(node_id, kind=node.kind, label=node.label, path=node.path)
    for edge in edges:
        graph.add_edge(edge.source, edge.target, relation=edge.relation)
    return graph


def _communities(graph: nx.Graph[str]) -> list[list[str]]:
    if graph.number_of_nodes() == 0:
        return []
    return [sorted(community) for community in nx.community.louvain_communities(graph, seed=42)]


def _god_nodes(graph: nx.Graph[str], limit: int = _GOD_NODE_LIMIT) -> list[str]:
    if graph.number_of_nodes() == 0:
        return []
    centrality = cast("dict[str, float]", nx.degree_centrality(graph))
    ranked = sorted(centrality.items(), key=lambda item: (-item[1], item[0]))
    return [node_id for node_id, _ in ranked[:limit]]
