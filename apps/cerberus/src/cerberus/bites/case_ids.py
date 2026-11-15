from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

from cerberus.bites.story_files import CASE_ID, FILE_ID
from cerberus.graph.parse import parse_typescript
from cerberus.ts_syntax import node_text, string_literal, walk_nodes

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tree_sitter import Node

_PY_TEST_NAME = re.compile(rf"test_({FILE_ID}(?:_[0-9]+)+)_(.+)")
_TS_CASE_ID = re.compile(rf"^({CASE_ID})(?=\s|$)")
_TS_TEST_CALL = re.compile(r"(?:test|it)(?:\.(?:concurrent|each|fails|for|only|runIf|sequential|skip|skipIf|todo))*")
_TS_TEST_FACTORIES = (".each", ".for", ".runIf", ".skipIf")


def list_python_tests(content: str) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(ast.parse(content)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            yield node


def split_python_test_name(name: str) -> tuple[str, str]:
    match = _PY_TEST_NAME.fullmatch(name)
    if not match:
        return "", name.removeprefix("test_").replace("_", " ")
    return match.group(1).replace("_", "."), match.group(2).replace("_", " ")


def _find_table(call: Node, name: str) -> Node | None:
    parent = call.parent
    while parent is not None:
        for declaration in parent.named_children:
            if declaration.type != "lexical_declaration":
                continue
            for binding in declaration.named_children:
                identifier = binding.child_by_field_name("name")
                value = binding.child_by_field_name("value")
                if (
                    identifier is not None
                    and node_text(identifier) == name
                    and value is not None
                    and value.type == "array"
                ):
                    return value
        parent = parent.parent
    return None


def _expand_titles(call: Node, function: Node, title: str) -> list[str]:
    if "%s" not in title.split(" ", 1)[0]:
        return [title]
    arrays = [node for node in walk_nodes(function) if node.type == "array"]
    if not arrays:
        arrays = [
            table
            for node in walk_nodes(function)
            if node.type == "identifier" and (table := _find_table(call, node_text(node))) is not None
        ]
    if not arrays:
        return [""]
    titles = []
    for row in arrays[0].named_children:
        cell = row.named_children[0] if row.type == "array" and row.named_children else row
        label = string_literal(cell)
        titles.append(title.replace("%s", label, 1) if label is not None else "")
    return titles


def _test_titles(call: Node) -> list[str]:
    function = call.child_by_field_name("function")
    arguments = call.child_by_field_name("arguments")
    if function is None or arguments is None:
        return []
    is_factory_call = function.type == "call_expression"
    callee_node = function.child_by_field_name("function") if is_factory_call else function
    if callee_node is None:
        return []
    callee = node_text(callee_node)
    if not _TS_TEST_CALL.fullmatch(callee) or callee.endswith(_TS_TEST_FACTORIES) != is_factory_call:
        return []
    title = string_literal(arguments.named_children[0]) if arguments.named_children else None
    return _expand_titles(call, function, title) if title is not None else [""]


def list_typescript_cases(path: str, content: str) -> Iterator[tuple[int, str]]:
    root = parse_typescript(path, content).root_node
    for node in walk_nodes(root):
        if node.type == "call_expression":
            for title in _test_titles(node):
                match = _TS_CASE_ID.match(title)
                yield node.start_point.row + 1, match.group(1) if match else ""
