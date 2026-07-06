from __future__ import annotations

import json
from typing import TYPE_CHECKING

import networkx as nx

if TYPE_CHECKING:
    from pathlib import Path


def load(graph_path: Path) -> nx.DiGraph[str]:
    """Load a graph.json as a DiGraph so an edge's stored source->target import/contains direction survives.

    `graph-query`'s traversal treats this as undirected (see `query.py`); only
    `graph-explain`'s single-node connection list needs the direction itself,
    to tell "this imports X" from "X imports this" the way graphify's own
    `explain` does.
    """
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    graph: nx.DiGraph[str] = nx.DiGraph()
    for node in data["nodes"]:
        graph.add_node(node["id"], **node)
    for edge in data["edges"]:
        graph.add_edge(edge["source"], edge["target"], relation=edge["relation"], confidence=edge["confidence"])
    return graph
