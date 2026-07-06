from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache

import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Node, Parser, Query, QueryCursor

_PY_SYMBOL_QUERY_SOURCE = """
(module (function_definition name: (identifier) @function.name))
(module (class_definition name: (identifier) @class.name))
"""

_PY_IMPORT_QUERY_SOURCE = """
(import_from_statement) @stmt
(import_statement) @stmt
"""

_TS_SYMBOL_QUERY_SOURCE = """
(program (function_declaration name: (identifier) @function.name))
(program (generator_function_declaration name: (identifier) @function.name))
(program (class_declaration name: (type_identifier) @class.name))
(program (abstract_class_declaration name: (type_identifier) @class.name))
(program (export_statement declaration: (function_declaration name: (identifier) @function.name)))
(program (export_statement declaration: (generator_function_declaration name: (identifier) @function.name)))
(program (export_statement declaration: (class_declaration name: (type_identifier) @class.name)))
(program (export_statement declaration: (abstract_class_declaration name: (type_identifier) @class.name)))
"""

_TS_IMPORT_QUERY_SOURCE = """
(import_statement source: (string (string_fragment) @source))
(export_statement source: (string (string_fragment) @source))
"""


# Every tree-sitter Language/Parser/Query below is built lazily and cached on
# first use, not at import time: constructing all six eagerly costs ~28ms
# regardless of whether the caller ever parses a single file (`graph-explain`/
# `graph-query` import this module transitively but never call `extract()`),
# and eagerly building the TS/TSX grammars also wastes time on a repo that
# only has Python.
@cache
def _py_language() -> Language:
    return Language(tspython.language())


@cache
def _ts_language() -> Language:
    return Language(tstypescript.language_typescript())


@cache
def _tsx_language() -> Language:
    return Language(tstypescript.language_tsx())


@cache
def _py_parser() -> Parser:
    return Parser(_py_language())


@cache
def _ts_parser() -> Parser:
    return Parser(_ts_language())


@cache
def _tsx_parser() -> Parser:
    return Parser(_tsx_language())


@cache
def _py_symbol_query() -> Query:
    return Query(_py_language(), _PY_SYMBOL_QUERY_SOURCE)


@cache
def _py_import_query() -> Query:
    return Query(_py_language(), _PY_IMPORT_QUERY_SOURCE)


@cache
def _ts_symbol_query() -> Query:
    return Query(_ts_language(), _TS_SYMBOL_QUERY_SOURCE)


@cache
def _tsx_symbol_query() -> Query:
    return Query(_tsx_language(), _TS_SYMBOL_QUERY_SOURCE)


@cache
def _ts_import_query() -> Query:
    return Query(_ts_language(), _TS_IMPORT_QUERY_SOURCE)


@cache
def _tsx_import_query() -> Query:
    return Query(_tsx_language(), _TS_IMPORT_QUERY_SOURCE)


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    line: int


@dataclass(frozen=True)
class PyImportRef:
    level: int
    dotted: str


@dataclass(frozen=True)
class Extracted:
    symbols: tuple[Symbol, ...] = ()
    py_imports: tuple[PyImportRef, ...] = field(default=())
    ts_specifiers: tuple[str, ...] = field(default=())


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _line(node: Node) -> int:
    return node.start_point[0] + 1


def _symbols_from_captures(captures: dict[str, list[Node]], source: bytes) -> tuple[Symbol, ...]:
    symbols = [Symbol(_text(node, source), "function", _line(node)) for node in captures.get("function.name", [])]
    symbols += [Symbol(_text(node, source), "class", _line(node)) for node in captures.get("class.name", [])]
    return tuple(symbols)


def _python_symbols(root: Node, source: bytes) -> tuple[Symbol, ...]:
    captures = QueryCursor(_py_symbol_query()).captures(root)
    return _symbols_from_captures(captures, source)


def _import_target_text(node: Node, source: bytes) -> str | None:
    if node.type == "dotted_name":
        return _text(node, source)
    if node.type == "aliased_import":
        inner = node.child_by_field_name("name")
        return _text(inner, source) if inner is not None else None
    return None


def _count_dots(import_prefix: Node) -> int:
    return sum(1 for child in import_prefix.children if child.type == ".")


def _relative_import_parts(node: Node, source: bytes) -> tuple[int, str | None]:
    prefix = next(child for child in node.children if child.type == "import_prefix")
    level = _count_dots(prefix)
    submodule = next((child for child in node.children if child.type == "dotted_name"), None)
    return level, (_text(submodule, source) if submodule is not None else None)


def _plain_import_refs(node: Node, source: bytes) -> list[PyImportRef]:
    refs = []
    for name_node in node.children_by_field_name("name"):
        target = _import_target_text(name_node, source)
        if target is not None:
            refs.append(PyImportRef(0, target))
    return refs


def _from_import_refs(node: Node, source: bytes) -> list[PyImportRef]:
    module_name = node.child_by_field_name("module_name")
    if module_name is None:
        return []
    if module_name.type == "dotted_name":
        return [PyImportRef(0, _text(module_name, source))]

    level, submodule = _relative_import_parts(module_name, source)
    if submodule is not None:
        return [PyImportRef(level, submodule)]

    refs = []
    for name_node in node.children_by_field_name("name"):
        target = _import_target_text(name_node, source)
        if target is not None:
            refs.append(PyImportRef(level, target))
    return refs


def _statement_refs(node: Node, source: bytes) -> list[PyImportRef]:
    if node.type == "import_statement":
        return _plain_import_refs(node, source)
    return _from_import_refs(node, source)


def _python_import_refs(root: Node, source: bytes) -> tuple[PyImportRef, ...]:
    captures = QueryCursor(_py_import_query()).captures(root)
    refs: list[PyImportRef] = []
    for stmt in captures.get("stmt", []):
        refs.extend(_statement_refs(stmt, source))
    return tuple(refs)


def _ts_specifiers(root: Node, source: bytes, query: Query) -> tuple[str, ...]:
    captures = QueryCursor(query).captures(root)
    return tuple(_text(node, source) for node in captures.get("source", []))


def extract(path: str, content: str) -> Extracted:
    source = content.encode("utf-8")
    if path.endswith(".py"):
        tree = _py_parser().parse(source)
        return Extracted(
            symbols=_python_symbols(tree.root_node, source),
            py_imports=_python_import_refs(tree.root_node, source),
        )
    if path.endswith(".tsx"):
        tree = _tsx_parser().parse(source)
        captures = QueryCursor(_tsx_symbol_query()).captures(tree.root_node)
        return Extracted(
            symbols=_symbols_from_captures(captures, source),
            ts_specifiers=_ts_specifiers(tree.root_node, source, _tsx_import_query()),
        )
    tree = _ts_parser().parse(source)
    captures = QueryCursor(_ts_symbol_query()).captures(tree.root_node)
    return Extracted(
        symbols=_symbols_from_captures(captures, source),
        ts_specifiers=_ts_specifiers(tree.root_node, source, _ts_import_query()),
    )
