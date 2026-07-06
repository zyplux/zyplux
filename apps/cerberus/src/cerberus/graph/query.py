from __future__ import annotations

from typing import cast

import networkx as nx

from cerberus.graph import search

_DEFAULT_SEED_LIMIT = 3


def _traverse(
    graph: nx.Graph[str], seeds: list[str], depth: int, *, dfs: bool
) -> tuple[set[str], list[tuple[str, str]]]:
    edge_walker = nx.dfs_edges if dfs else nx.bfs_edges
    nodes: set[str] = set(seeds)
    edges: list[tuple[str, str]] = []
    seen: set[frozenset[str]] = set()
    for seed in seeds:
        seed_edges = cast("list[tuple[str, str]]", list(edge_walker(graph, seed, depth_limit=depth)))
        for source, target in seed_edges:
            key = frozenset((source, target))
            if key in seen:
                continue
            seen.add(key)
            edges.append((source, target))
            nodes.add(source)
            nodes.add(target)
    return nodes, edges


def _render(graph: nx.Graph[str], nodes: set[str], edges: list[tuple[str, str]], budget: int) -> str:
    lines: list[str] = []
    used = 0

    def emit(line: str) -> bool:
        nonlocal used
        if used + len(line) + 1 > budget:
            return False
        lines.append(line)
        used += len(line) + 1
        return True

    for node_id in sorted(nodes, key=lambda n: (-graph.degree(n), n)):
        data = graph.nodes[node_id]
        line = (
            f"NODE {data.get('label', node_id)} "
            f"[src={data.get('source_file', '')} loc={data.get('source_location', '')} "
            f"community={data.get('community', '')}]"
        )
        if not emit(line):
            return "\n".join(lines)

    for source, target in edges:
        edge_data = graph.edges[source, target]
        line = (
            f"EDGE {graph.nodes[source].get('label', source)} -[{edge_data['relation']}]- "
            f"{graph.nodes[target].get('label', target)} [{edge_data['confidence']}]"
        )
        if not emit(line):
            return "\n".join(lines)

    return "\n".join(lines)


def query_text(graph: nx.DiGraph[str], question: str, *, depth: int = 2, dfs: bool = False, budget: int = 2000) -> str:
    """Seed a BFS/DFS traversal from the best free-text matches and render it as budget-truncated text.

    Seeding is a plain substring/token score (see `search.py`) rather than
    graphify's IDF-weighted, trigram-indexed ranking — this runs once per CLI
    invocation, so the scale-oriented optimizations graphify needs for a
    persistent query server aren't the bottleneck here.

    Traversal itself treats the graph as undirected (a view, not a copy) —
    unlike `explain.py`'s single-node connection list, "what's reachable
    around X" should follow an edge either way, matching graphify's own
    `query` (only its `explain` forces direction).
    """
    seeds = search.pick_seeds(graph, question, limit=_DEFAULT_SEED_LIMIT)
    if not seeds:
        return "No matching nodes found."

    undirected = graph.to_undirected(as_view=True)
    nodes, edges = _traverse(undirected, seeds, depth, dfs=dfs)
    mode = "DFS" if dfs else "BFS"
    start_labels = [graph.nodes[seed].get("label", seed) for seed in seeds]
    header = f"Traversal: {mode} depth={depth} | Start: {start_labels} | {len(nodes)} nodes found\n\n"
    return header + _render(undirected, nodes, edges, budget)
