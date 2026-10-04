from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tree_sitter import Node

from cerberus.graph.parse import parse_typescript


def walk_nodes(node: Node) -> Iterator[Node]:
    yield node
    for child in node.named_children:
        yield from walk_nodes(child)


def node_text(node: Node) -> str:
    return node.text.decode() if node.text is not None else ""


def string_literal(node: Node | None) -> str | None:
    if node is None or node.type not in {"string", "template_string"}:
        return None
    if any(child.type == "template_substitution" for child in node.named_children):
        return None
    return node_text(node)[1:-1]


def object_fields(node: Node) -> dict[str, Node]:
    fields = {}
    for pair in node.named_children:
        if pair.type != "pair":
            continue
        key, value = pair.child_by_field_name("key"), pair.child_by_field_name("value")
        if key is not None and value is not None:
            fields[string_literal(key) or node_text(key)] = value
    return fields


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
