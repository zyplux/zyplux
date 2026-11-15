"""Read TypeScript string literals and JSONC configuration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from cerberus.graph.parse import parse_typescript
from cerberus.syntax.tree_sitter_nodes import get_node_text, walk_nodes

if TYPE_CHECKING:
    from tree_sitter import Node


def string_literal(node: Node | None) -> str | None:
    if node is None or node.type not in {"string", "template_string"}:
        return None
    if any(child.type == "template_substitution" for child in node.named_children):
        return None
    return get_node_text(node)[1:-1]


def parse_jsonc(content: str) -> dict[str, Any]:
    tree = parse_typescript("config.ts", f"({content})")
    objects = [node for node in walk_nodes(tree.root_node) if node.type == "object"]
    if tree.root_node.has_error or not objects:
        message = "configuration must be a valid JSONC object"
        raise ValueError(message)
    source = f"({content})".encode()
    removals = [(node.start_byte, node.end_byte) for node in walk_nodes(tree.root_node) if node.type == "comment"]
    for node in walk_nodes(tree.root_node):
        for index, child in enumerate(node.children[:-1]):
            if child.type == "," and node.children[index + 1].type in {"}", "]"}:
                removals.append((child.start_byte, child.end_byte))
    for start, end in sorted(removals, reverse=True):
        source = source[:start] + b" " * (end - start) + source[end:]
    parsed = json.loads(source[1:-1])
    if not isinstance(parsed, dict):
        message = "configuration must be an object"
        raise TypeError(message)
    return parsed
