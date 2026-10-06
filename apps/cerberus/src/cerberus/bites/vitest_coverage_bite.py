from __future__ import annotations

import re
from typing import TYPE_CHECKING

from cerberus.graph.parse import parse_typescript
from cerberus.model import CheckResult, Scope
from cerberus.package_test_script import parse_test_script
from cerberus.shell_commands import get_shell_parser, list_command_args
from cerberus.ts_syntax import node_text, string_literal, walk_nodes

if TYPE_CHECKING:
    from tree_sitter import Node

    from cerberus.context import Context
    from cerberus.model import Repo

ID = "vitest_coverage"
SUMMARY = "Root Vitest coverage thresholds enforce the configured coverage floor"
SCOPE = Scope.CONTENT
_ROOT_CONFIG = re.compile(r"^vitest\.config\.[cm]?[jt]s$")
_METRICS = ("branches", "functions", "lines", "statements")


def _list_bindings(root: Node) -> tuple[dict[str, Node], set[str]]:
    bindings = {}
    helpers = set()
    for statement in root.named_children:
        declaration = statement.child_by_field_name("declaration") or statement
        if declaration.type == "lexical_declaration" and declaration.children[0].type == "const":
            for binding in declaration.named_children:
                name, initializer = binding.child_by_field_name("name"), binding.child_by_field_name("value")
                if name is not None and name.type == "identifier" and initializer is not None:
                    bindings[node_text(name)] = initializer
        if (
            declaration.type == "import_statement"
            and string_literal(declaration.child_by_field_name("source")) in {"vitest/config", "vite"}
            and not any(child.type == "type" for child in declaration.children)
        ):
            for specifier in walk_nodes(declaration):
                if (
                    specifier.type == "import_specifier"
                    and not any(child.type == "type" for child in specifier.children)
                    and node_text(specifier.child_by_field_name("name") or specifier) == "defineConfig"
                ):
                    helpers.add(
                        node_text(
                            specifier.child_by_field_name("alias") or specifier.child_by_field_name("name") or specifier
                        )
                    )
    return bindings, helpers


def _resolve_literal(
    node: Node | None, bindings: dict[str, Node], helpers: set[str], active: frozenset[str] = frozenset()
) -> Node | None:
    if node is None:
        return None
    if node.type in {"identifier", "shorthand_property_identifier"}:
        name = node_text(node)
        return None if name in active else _resolve_literal(bindings.get(name), bindings, helpers, active | {name})
    if node.type in {"parenthesized_expression", "satisfies_expression", "as_expression"}:
        return _resolve_literal(node.named_children[0], bindings, helpers, active)
    if node.type == "call_expression":
        callee, arguments = node.child_by_field_name("function"), node.child_by_field_name("arguments")
        if (
            callee is not None
            and node_text(callee) in helpers
            and node_text(callee) not in bindings
            and arguments is not None
            and len(arguments.named_children) == 1
        ):
            node = arguments.named_children[0]
        else:
            node = None
        return _resolve_literal(node, bindings, helpers, active)
    return node


def _resolve_config(node: Node | None, bindings: dict[str, Node], helpers: set[str]) -> Node | None:
    node = _resolve_literal(node, bindings, helpers)
    if node is None:
        return None
    if node.type in {"arrow_function", "function_expression"}:
        body, parameters = node.child_by_field_name("body"), node.child_by_field_name("parameters")
        shadowed = (
            frozenset(
                node_text(parameter)
                for parameter in walk_nodes(parameters)
                if parameter.type in {"identifier", "shorthand_property_identifier_pattern"}
            )
            if parameters is not None
            else frozenset()
        )
        if body is not None and body.type == "statement_block":
            statements = [statement for statement in body.named_children if statement.type != "comment"]
            body = (
                statements[0].named_children[0]
                if len(statements) == 1 and statements[0].type == "return_statement" and statements[0].named_children
                else None
            )
        if body is not None and any(
            reference.type in {"identifier", "shorthand_property_identifier"} and node_text(reference) in shadowed
            for reference in walk_nodes(body)
        ):
            body = None
        return _resolve_literal(body, bindings, helpers, shadowed)
    return node


def _resolve_fields(
    node: Node | None, bindings: dict[str, Node], helpers: set[str], active: frozenset[int] = frozenset()
) -> dict[str, Node] | None:
    node = _resolve_literal(node, bindings, helpers)
    if node is None or node.type != "object" or node.id in active:
        return None
    fields = {}
    for field in node.named_children:
        if field.type == "spread_element":
            spread = _resolve_fields(field.named_children[0], bindings, helpers, active | {node.id})
            if spread is None:
                return None
            fields.update(spread)
        elif field.type == "pair":
            key, initializer = field.child_by_field_name("key"), field.child_by_field_name("value")
            if key is None or initializer is None or key.type == "computed_property_name":
                return None
            fields[string_literal(key) or node_text(key)] = initializer
        elif field.type == "shorthand_property_identifier":
            fields[node_text(field)] = field
        elif field.type != "comment":
            return None
    return fields


def _find_coverage(root: Node) -> tuple[Node | None, dict[str, Node], set[str]]:
    bindings, helpers = _list_bindings(root)

    def resolve(node: Node | None) -> Node | None:
        return _resolve_literal(node, bindings, helpers)

    for statement in root.named_children:
        if statement.type != "export_statement" or not any(child.type == "default" for child in statement.children):
            continue
        config = _resolve_config(statement.child_by_field_name("value"), bindings, helpers)
        test = resolve((_resolve_fields(config, bindings, helpers) or {}).get("test"))
        coverage = resolve((_resolve_fields(test, bindings, helpers) or {}).get("coverage"))
        return coverage, bindings, helpers
    return None, bindings, helpers


def _enables_coverage(script: str, *, configured: bool) -> bool:
    root = get_shell_parser().parse(script.encode()).root_node
    if root.has_error:
        return False
    command = next((child for child in root.named_children if child.type != "comment"), None)
    while command is not None and command.type in {"list", "pipeline", "redirected_statement"}:
        command = next((child for child in command.named_children if child.type != "comment"), None)
    if command is None or command.type != "command":
        return configured
    args = list_command_args(command)
    if not args:
        return False
    prefixes = [("vitest",), ("pnpm", "exec", "vitest"), ("pnpm", "vitest"), ("npx", "vitest"), ("bunx", "vitest")]
    if not any(tuple(args[: len(prefix)]) == prefix for prefix in prefixes):
        return configured
    enabled = configured
    for index, arg in enumerate(args):
        flag, separator, setting = arg.partition("=")
        if flag in {"--coverage", "--coverage.enabled"}:
            enabled = setting == "true" if separator else index + 1 == len(args) or args[index + 1] != "false"
    return enabled


def _check_config(path: str, content: str, floor: int, script: str, res: CheckResult) -> None:
    tree = parse_typescript(path, content)
    if tree.root_node.has_error:
        res.fail(f"{path}: invalid TypeScript coverage configuration")
        return
    coverage, bindings, helpers = _find_coverage(tree.root_node)
    fields = _resolve_fields(coverage, bindings, helpers) or {}
    thresholds = _resolve_literal(fields.get("thresholds"), bindings, helpers)
    metrics = _resolve_fields(thresholds, bindings, helpers)
    if metrics is None:
        res.fail(
            f"{path}: exported test.coverage.thresholds must resolve to a literal object enforcing at least {floor}%"
        )
        return
    for key in _METRICS:
        threshold = _resolve_literal(metrics.get(key), bindings, helpers)
        if threshold is None or threshold.type != "number":
            res.fail(f"{path} coverage.thresholds has no literal `{key}`; must be set to at least {floor}")
        elif float(node_text(threshold)) < floor:
            res.fail(f"{path} coverage.thresholds.{key} is {float(node_text(threshold))}, below the required {floor}")
    enabled = _resolve_literal(fields.get("enabled"), bindings, helpers)
    if not _enables_coverage(script, configured=enabled is not None and enabled.type == "true"):
        res.fail(f"{path}: enable coverage with test.coverage.enabled: true or the root test script's --coverage flag")


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    paths = ctx.paths(repo)
    configs = [path for path in paths if _ROOT_CONFIG.fullmatch(path)]
    if not configs:
        if any(path.endswith((".test.ts", ".test.tsx", ".spec.ts")) for path in paths):
            res.fail("TypeScript tests require a root vitest.config with coverage thresholds")
        else:
            res.skip("no root Vitest coverage configuration or TypeScript tests")
        return res
    floor = ctx.config.vitest_min_coverage
    script = parse_test_script(ctx.file(repo, "package.json") or "{}")
    for path in configs:
        content = ctx.file(repo, path)
        if content is None:
            res.error(f"could not read {path}")
            continue
        _check_config(path, content, floor, script, res)
    if not res.problems:
        res.ok(f"Vitest coverage gate enforces >= {floor}%")
    return res
