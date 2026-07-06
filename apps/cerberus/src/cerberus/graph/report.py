from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from cerberus.graph.model import Edge, GraphResult, Node

_GRAPH_JSON = "graph.json"


def _node_community_index(communities: list[list[str]]) -> dict[str, int]:
    return {node_id: index for index, members in enumerate(communities) for node_id in members}


def _node_json(node: Node, community_index: dict[str, int]) -> dict[str, Any]:
    return {
        "id": node.id,
        "kind": node.kind,
        "label": node.label,
        "path": node.path,
        "source_file": node.path,
        "file_type": "code",
        "source_location": f"L{node.line}",
        "community": community_index.get(node.id),
    }


def _edge_json(edge: Edge) -> dict[str, Any]:
    return {"source": edge.source, "target": edge.target, "relation": edge.relation, "confidence": edge.confidence}


def _to_json(result: GraphResult) -> dict[str, Any]:
    community_index = _node_community_index(result.communities)
    return {
        "nodes": [_node_json(node, community_index) for node in result.nodes],
        "edges": [_edge_json(edge) for edge in result.edges],
        "communities": result.communities,
        "god_nodes": result.god_nodes,
    }


def write(result: GraphResult, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / _GRAPH_JSON).write_text(json.dumps(_to_json(result), indent=2) + "\n")
