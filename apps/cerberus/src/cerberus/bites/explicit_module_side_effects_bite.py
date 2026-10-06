from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from cerberus.architecture import build_export_map, is_library, list_targets, run_package_policy
from cerberus.graph.parse import parse_typescript
from cerberus.model import Scope
from cerberus.ts_syntax import node_text, string_literal

if TYPE_CHECKING:
    from tree_sitter import Node

    from cerberus.context import Context
    from cerberus.graph.resolve_ts import PackageInfo
    from cerberus.model import CheckResult, Repo

ID = "explicit_module_side_effects"
SUMMARY = "Libraries declare side effects and preserve modules that execute registration or initialization"
SCOPE = Scope.CONTENT
_FUNCTION_NODES = {
    "arrow_function",
    "function_expression",
    "function_declaration",
    "generator_function_declaration",
    "generator_function",
    "method_definition",
}


def _list_published_modules(module: str, package: PackageInfo) -> set[str]:
    exports = build_export_map(package.manifest.get("exports"))
    published = build_export_map(package.manifest.get("publishConfig", {}).get("exports", {}))
    modules = set()
    for key, entry in exports.items():
        for source in list_targets(entry):
            pattern = source.removeprefix("./")
            prefix, wildcard, suffix = pattern.partition("*")
            if module != pattern and not (wildcard and module.startswith(prefix) and module.endswith(suffix)):
                continue
            match = module[len(prefix) : len(module) - len(suffix) if suffix else None] if wildcard else ""
            modules.update(
                target.removeprefix("./").replace("*", match)
                for target in list_targets(published.get(key))
                if target.endswith((".js", ".mjs", ".cjs"))
            )
    return modules


def _is_commonjs_export(node: Node | None) -> bool:
    if node is None or node.type not in {"member_expression", "subscript_expression"}:
        return False
    receiver = node.child_by_field_name("object")
    member = node.child_by_field_name("property") or node.child_by_field_name("index")
    if receiver is None or member is None or member.type not in {"property_identifier", "string", "number"}:
        return False
    if node_text(receiver) == "module":
        return (string_literal(member) or node_text(member)) == "exports"
    return node_text(receiver) == "exports" or _is_commonjs_export(receiver)


def _executes_export(node: Node) -> bool:
    if node.type in _FUNCTION_NODES:
        return False
    return node.type in {
        "call_expression",
        "new_expression",
        "assignment_expression",
        "augmented_assignment_expression",
        "update_expression",
        "await_expression",
    } or any(_executes_export(child) for child in node.named_children)


def _executes_statement(node: Node, functions: dict[str, Node], active: frozenset[str] = frozenset()) -> bool:
    if node.type == "expression_statement":
        expression = node.named_children[0]
        if expression.type == "assignment_expression" and _is_commonjs_export(expression.child_by_field_name("left")):
            initializer = expression.child_by_field_name("right")
            return initializer is not None and _executes_export(initializer)
        return expression.type != "string"
    if node.type in _FUNCTION_NODES:
        return False
    if node.type == "call_expression":
        callee = node.child_by_field_name("function")
        name = node_text(callee) if callee is not None else ""
        function = functions.get(name)
        if function is not None and name not in active:
            body = function.child_by_field_name("body")
            if body is not None and _executes_statement(body, functions, active | {name}):
                return True
    return any(_executes_statement(child, functions, active) for child in node.named_children)


def _executes_initialization(root: Node) -> bool:
    functions = {}
    for statement in root.named_children:
        declaration = statement.child_by_field_name("declaration") or statement
        if declaration.type == "function_declaration":
            name = declaration.child_by_field_name("name")
            if name is not None:
                functions[node_text(name)] = declaration
        for binding in declaration.named_children:
            name, initializer = binding.child_by_field_name("name"), binding.child_by_field_name("value")
            if (
                name is not None
                and initializer is not None
                and initializer.type in {"arrow_function", "function_expression"}
            ):
                functions[node_text(name)] = initializer
    return _executes_statement(root, functions)


def run(repo: Repo, ctx: Context) -> CheckResult:
    def inspect(_name: str, package: PackageInfo) -> list[str]:
        if not is_library(package):
            return []
        metadata = package.manifest.get("sideEffects")
        if metadata is not False and not (
            isinstance(metadata, list) and all(isinstance(entry, str) for entry in metadata)
        ):
            return ["declare sideEffects as false or explicit module patterns"]
        findings = []
        prefix = f"{package.directory}/src/"
        for path in ctx.paths(repo):
            if not path.startswith(prefix) or PurePosixPath(path).suffix not in {
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".mjs",
                ".mts",
                ".cts",
                ".cjs",
            }:
                continue
            content = ctx.file(repo, path)
            if content is None:
                continue
            tree = parse_typescript(path, content)
            if not _executes_initialization(tree.root_node):
                continue
            module = path.removeprefix(f"{package.directory}/")
            findings.extend(
                f"{path} executes a top-level statement; list {target} in sideEffects"
                for target in sorted({module, *_list_published_modules(module, package)})
                if metadata is False
                or not any(PurePosixPath(target).full_match(pattern.removeprefix("./")) for pattern in metadata)
            )
        return findings

    return run_package_policy(repo, ctx, ID, inspect)
