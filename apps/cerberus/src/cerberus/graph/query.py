from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.graph import search

if TYPE_CHECKING:
    import networkx as nx

_DEFAULT_SEED_LIMIT = 3
_HUB_DEGREE_FLOOR = 50
_HUB_PERCENTILE = 0.99


def _hub_threshold(graph: nx.Graph[str]) -> int:
    """The 99th-percentile node degree, floored at 50 — mirrors graphify's own traversal cap."""
    degrees = sorted(dict(graph.degree()).values())
    if not degrees:
        return _HUB_DEGREE_FLOOR
    return max(_HUB_DEGREE_FLOOR, degrees[int(len(degrees) * _HUB_PERCENTILE)])


def _is_hub(graph: nx.Graph[str], node_id: str, seed_set: set[str], hub_threshold: int) -> bool:
    return node_id not in seed_set and graph.degree(node_id) >= hub_threshold


def _bfs_nodes(graph: nx.Graph[str], seeds: list[str], depth: int, seed_set: set[str], hub_threshold: int) -> set[str]:
    visited = set(seeds)
    frontier = set(seeds)
    for _ in range(depth):
        next_frontier: set[str] = set()
        for node_id in frontier:
            if _is_hub(graph, node_id, seed_set, hub_threshold):
                continue
            for neighbor_id in graph.neighbors(node_id):
                if neighbor_id not in visited:
                    next_frontier.add(neighbor_id)
        visited.update(next_frontier)
        frontier = next_frontier
    return visited


def _dfs_nodes(graph: nx.Graph[str], seeds: list[str], depth: int, seed_set: set[str], hub_threshold: int) -> set[str]:
    visited: set[str] = set()
    stack = [(node_id, 0) for node_id in reversed(seeds)]
    while stack:
        node_id, hop = stack.pop()
        if node_id in visited or hop > depth:
            continue
        visited.add(node_id)
        if _is_hub(graph, node_id, seed_set, hub_threshold):
            continue
        stack.extend((neighbor_id, hop + 1) for neighbor_id in graph.neighbors(node_id) if neighbor_id not in visited)
    return visited


def _induced_edges(graph: nx.Graph[str], nodes: set[str]) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    seen: set[frozenset[str]] = set()
    for node_id in nodes:
        for neighbor_id in graph.neighbors(node_id):
            if neighbor_id not in nodes:
                continue
            key = frozenset((node_id, neighbor_id))
            if key in seen:
                continue
            seen.add(key)
            edges.append((node_id, neighbor_id))
    return edges


def _traverse(
    graph: nx.Graph[str], seeds: list[str], depth: int, *, dfs: bool
) -> tuple[set[str], list[tuple[str, str]]]:
    """BFS/DFS to `depth` hops, refusing to expand *through* a hub node.

    A hub is any non-seed node at or above the 99th-percentile degree
    (floored at 50) — without this cap, a single god-node one hop from a
    seed (e.g. a shared model/util module) pulls in its entire, largely
    unrelated neighborhood, ballooning the result. A hub is still visited and
    shown; its own neighbors just don't join the walk through it.
    """
    seed_set = set(seeds)
    hub_threshold = _hub_threshold(graph)
    nodes = (
        _dfs_nodes(graph, seeds, depth, seed_set, hub_threshold)
        if dfs
        else _bfs_nodes(graph, seeds, depth, seed_set, hub_threshold)
    )
    return nodes, _induced_edges(graph, nodes)


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
            f"NODE {data.get('label', node_id)} [src={data.get('source_file', '')} "
            f"loc={data.get('source_location', '')} community={data.get('community', '')}]"
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

    Seeding uses a substring/token score with inverse-document-frequency term
    weighting (see `search.py`) — simpler than graphify's trigram-indexed
    ranking, since this runs once per CLI invocation, so the scale-oriented
    optimizations graphify needs for a persistent query server aren't the
    bottleneck here.

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
