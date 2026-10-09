from __future__ import annotations

import shlex
from functools import cache
from typing import TYPE_CHECKING

import tree_sitter_bash
from tree_sitter import Language, Parser

from cerberus.ts_syntax import node_text, walk_nodes

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tree_sitter import Node


@cache
def get_shell_parser() -> Parser:
    return Parser(Language(tree_sitter_bash.language()))


def list_command_args(command: Node) -> tuple[str, ...]:
    words = [*command.children_by_field_name("name"), *command.children_by_field_name("argument")]
    try:
        return tuple(shlex.split(node_text(word))[0] for word in words)
    except ValueError, IndexError:
        return ()


def matches_tool_command(command: tuple[str, ...], required: tuple[str, ...]) -> bool:
    if set(command) & {"--help", "-h", "--version", "-V"}:
        return False
    if required[:2] in {("uv", "run"), ("pnpm", "run")} and command[:3] != required[:3]:
        return False
    if required[:3] == ("pnpm", "run", "knip") and ("--config" in command) != ("--config" in required):
        return False
    positional = tuple(arg for arg in command if not arg.startswith("-"))
    expected = tuple(arg for arg in required if not arg.startswith("-"))
    return positional[: len(expected)] == expected and all(arg in command for arg in required if arg.startswith("-"))


def _list_commands(node: Node, manifests: frozenset[str]) -> Iterator[tuple[str, ...]]:
    match node.type:
        case "command":
            yield list_command_args(node)
        case "program" | "redirected_statement":
            for index, child in enumerate(node.children):
                if index + 1 < len(node.children) and node.children[index + 1].type == "&":
                    continue
                yield from _list_commands(child, manifests)
        case "if_statement":
            yield from _list_manifest_commands(node, manifests)
        case "list" if any(child.type == "&&" for child in node.children):
            if not any(
                list_command_args(command)[:1] == ("false",)
                for command in walk_nodes(node)
                if command.type == "command"
            ):
                for child in node.named_children:
                    yield from _list_commands(child, manifests)
        case "list":
            yield from _list_empty_pytest_commands(node)


def _list_manifest_commands(node: Node, manifests: frozenset[str]) -> Iterator[tuple[str, ...]]:
    condition = node.child_by_field_name("condition")
    if condition is None:
        return
    match list_command_args(condition):
        case ("test", "-f", manifest) if manifest in manifests:
            if any(child.type in {"else_clause", "elif_clause"} for child in node.named_children):
                return
            for child in node.named_children:
                if child != condition:
                    yield from _list_commands(child, manifests)


def _list_empty_pytest_commands(node: Node) -> Iterator[tuple[str, ...]]:
    match node.named_children:
        case [pytest, empty_exit] if any(child.type == "||" for child in node.children):
            args = list_command_args(pytest)
            if args[:3] == ("uv", "run", "pytest") and list_command_args(empty_exit) == ("test", "$?", "-eq", "5"):
                yield args


def list_required_commands(script: str, manifests: frozenset[str]) -> list[tuple[str, ...]]:
    source = "\n".join(line.removeprefix("@") for line in script.splitlines())
    root = get_shell_parser().parse(source.encode()).root_node
    if root.has_error:
        return []
    return [args for args in _list_commands(root, manifests) if args]


def list_shell_commands(script: str) -> list[tuple[str, ...]]:
    source = "\n".join(line.lstrip("@-") for line in script.splitlines())
    root = get_shell_parser().parse(source.encode()).root_node
    return [args for node in walk_nodes(root) if node.type == "command" and (args := list_command_args(node))]
