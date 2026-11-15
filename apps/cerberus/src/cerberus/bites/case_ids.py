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
_TS_ID_PLACEHOLDER = re.compile(r"%[sdif#$]")
_TS_TEST_MODIFIERS = re.compile(r"(?:\.(?:concurrent|each|fails|for|only|runIf|sequential|skip|skipIf|todo))*")
_TS_TEST_FACTORIES = (".each", ".for", ".runIf", ".skipIf")


def _list_pytest_cases(body: list[ast.stmt]) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            yield node
        elif (
            isinstance(node, ast.ClassDef)
            and node.name.startswith("Test")
            and not any(
                isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and member.name in {"__init__", "__new__"}
                for member in node.body
            )
        ):
            yield from _list_pytest_cases(node.body)


def list_python_tests(content: str) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    return _list_pytest_cases(ast.parse(content).body)


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
    placeholder = _TS_ID_PLACEHOLDER.search(title.split(" ", 1)[0])
    if placeholder is None:
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
    specifier = placeholder.group()
    titles = []
    for index, row in enumerate(arrays[0].named_children):
        cell = row.named_children[0] if row.type == "array" and row.named_children else row
        if specifier in {"%#", "%$"}:
            label = str(index + (specifier == "%$"))
        elif cell.type == "number" and node_text(cell).isdecimal():
            label = node_text(cell)
        else:
            label = string_literal(cell)
            if specifier != "%s" and label is not None and not label.isdecimal():
                label = None
        titles.append(title.replace(specifier, label, 1) if label is not None else "")
    return titles


def _find_test_source(node: Node | None) -> str:
    if node is None:
        return ""
    if node.type == "identifier":
        return node_text(node)
    function = node.child_by_field_name("function")
    if (
        function is not None
        and (method := function.child_by_field_name("property")) is not None
        and node_text(method) == "extend"
    ):
        return _find_test_source(function.child_by_field_name("object"))
    return ""


def _bind_test_imports(statement: Node, bindings: set[str]) -> None:
    for node in walk_nodes(statement):
        if node.type != "import_specifier" or (name := node.child_by_field_name("name")) is None:
            continue
        local = node_text(node.child_by_field_name("alias") or name)
        if node_text(name) in {"test", "it"}:
            bindings.add(local)
        else:
            bindings.discard(local)


def _list_test_bindings(scope: Node, inherited: set[str]) -> set[str]:
    bindings = inherited.copy()
    for statement in scope.named_children:
        if statement.type == "import_statement":
            _bind_test_imports(statement, bindings)
        elif statement.type in {"lexical_declaration", "variable_declaration"}:
            for declaration in statement.named_children:
                name = declaration.child_by_field_name("name")
                if name is not None and name.type == "identifier":
                    source = _find_test_source(declaration.child_by_field_name("value"))
                    if source in bindings:
                        bindings.add(node_text(name))
                    else:
                        bindings.discard(node_text(name))
        elif statement.type == "function_declaration" and (name := statement.child_by_field_name("name")) is not None:
            bindings.discard(node_text(name))
    return bindings


def _test_titles(call: Node, bindings: set[str]) -> list[str]:
    function = call.child_by_field_name("function")
    arguments = call.child_by_field_name("arguments")
    if function is None or arguments is None:
        return []
    is_factory_call = function.type == "call_expression"
    callee_node = function.child_by_field_name("function") if is_factory_call else function
    if callee_node is None:
        return []
    callee, dot, suffix = node_text(callee_node).partition(".")
    modifiers = dot + suffix
    if (
        callee not in bindings
        or not _TS_TEST_MODIFIERS.fullmatch(modifiers)
        or modifiers.endswith(_TS_TEST_FACTORIES) != is_factory_call
    ):
        return []
    title = string_literal(arguments.named_children[0]) if arguments.named_children else None
    return _expand_titles(call, function, title) if title is not None else [""]


def _list_typescript_cases(node: Node, bindings: set[str]) -> Iterator[tuple[int, str]]:
    parameters = node.child_by_field_name("parameters") or node.child_by_field_name("parameter")
    if parameters is not None:
        names = {
            node_text(parameter)
            for parameter in walk_nodes(parameters)
            if parameter.type in {"identifier", "shorthand_property_identifier_pattern"}
        }
        bindings = bindings.difference(names)
    if node.type in {"program", "statement_block"}:
        bindings = _list_test_bindings(node, bindings)
    if node.type == "call_expression" and (titles := _test_titles(node, bindings)):
        for title in titles:
            match = _TS_CASE_ID.match(title)
            yield node.start_point.row + 1, match.group(1) if match else ""
        return
    for child in node.named_children:
        yield from _list_typescript_cases(child, bindings)


def list_typescript_cases(path: str, content: str) -> Iterator[tuple[int, str]]:
    return _list_typescript_cases(parse_typescript(path, content).root_node, {"test", "it"})
