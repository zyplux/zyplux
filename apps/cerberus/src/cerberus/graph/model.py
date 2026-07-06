from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    label: str
    path: str
    line: int = 1


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    relation: str
    confidence: str = "EXTRACTED"


@dataclass(frozen=True)
class GraphResult:
    nodes: list[Node]
    edges: list[Edge]
    communities: list[list[str]] = field(default_factory=list)
    god_nodes: list[str] = field(default_factory=list)
