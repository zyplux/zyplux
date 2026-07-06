from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerberus.graph import search

if TYPE_CHECKING:
    import networkx as nx

_NEIGHBOR_LIMIT = 20


def _connections(graph: nx.DiGraph[str], node_id: str) -> list[tuple[str, str, dict[str, Any]]]:
    outgoing = [("out", target, graph.edges[node_id, target]) for target in graph.successors(node_id)]
    incoming = [("in", source, graph.edges[source, node_id]) for source in graph.predecessors(node_id)]
    return sorted(outgoing + incoming, key=lambda item: (-graph.degree(item[1]), item[1]))


def explain_text(graph: nx.DiGraph[str], query: str) -> str:
    node_id = search.best_match(graph, query)
    if node_id is None:
        return f"No node matching '{query}' found."

    data = graph.nodes[node_id]
    lines = [
        f"Node: {data.get('label', node_id)}",
        f"  ID:        {node_id}",
        f"  Source:    {data.get('source_file', '')} {data.get('source_location', '')}".rstrip(),
        f"  Type:      {data.get('file_type', '')}",
        f"  Community: {data.get('community', '')}",
        f"  Degree:    {graph.degree(node_id)}",
    ]

    connections = _connections(graph, node_id)
    if connections:
        lines.extend(["", f"Connections ({len(connections)}):"])
        for direction, neighbor_id, edge_data in connections[:_NEIGHBOR_LIMIT]:
            label = graph.nodes[neighbor_id].get("label", neighbor_id)
            arrow = "-->" if direction == "out" else "<--"
            lines.append(f"  {arrow} {label} [{edge_data['relation']}] [{edge_data['confidence']}]")
        remaining = len(connections) - _NEIGHBOR_LIMIT
        if remaining > 0:
            lines.append(f"  ... and {remaining} more")
    return "\n".join(lines)
