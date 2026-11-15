"""Traverse Tree-sitter named nodes and read their source text."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tree_sitter import Node


def walk_nodes(node: Node) -> Iterator[Node]:
    yield node
    for child in node.named_children:
        yield from walk_nodes(child)


def get_node_text(node: Node) -> str:
    return node.text.decode() if node.text is not None else ""
