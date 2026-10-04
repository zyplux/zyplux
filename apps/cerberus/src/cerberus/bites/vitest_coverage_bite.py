from __future__ import annotations

import re
from typing import TYPE_CHECKING

from cerberus.graph.parse import parse_typescript
from cerberus.model import CheckResult, Scope
from cerberus.ts_syntax import node_text, object_fields, walk_nodes

if TYPE_CHECKING:
    from tree_sitter import Node

    from cerberus.context import Context
    from cerberus.model import Repo

ID = "vitest_coverage"
SUMMARY = "Root Vitest coverage thresholds enforce the configured coverage floor"
SCOPE = Scope.CONTENT
_ROOT_CONFIG = re.compile(r"^vitest\.config\.[cm]?[jt]s$")
_METRICS = ("branches", "functions", "lines", "statements")


def _find_thresholds(root: Node) -> Node | None:
    for node in walk_nodes(root):
        if node.type != "export_statement" or not any(child.type == "default" for child in node.children):
            continue
        for config in walk_nodes(node):
            if config.type != "object":
                continue
            test = object_fields(config).get("test")
            coverage = object_fields(test).get("coverage") if test is not None else None
            if coverage is not None:
                return object_fields(coverage).get("thresholds")
    return None


def _check_config(path: str, content: str, floor: int, res: CheckResult) -> None:
    tree = parse_typescript(path, content)
    thresholds = _find_thresholds(tree.root_node)
    if tree.root_node.has_error:
        res.fail(f"{path}: invalid TypeScript coverage configuration")
    elif thresholds is None or thresholds.type != "object":
        res.fail(f"{path}: exported test.coverage.thresholds must be a literal object enforcing at least {floor}%")
    else:
        fields = object_fields(thresholds)
        for key in _METRICS:
            threshold = fields.get(key)
            if threshold is None or threshold.type != "number":
                res.fail(f"{path} coverage.thresholds has no literal `{key}`; must be set to at least {floor}")
            elif float(node_text(threshold)) < floor:
                res.fail(
                    f"{path} coverage.thresholds.{key} is {float(node_text(threshold))}, below the required {floor}"
                )


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
    for path in configs:
        content = ctx.file(repo, path)
        if content is None:
            res.error(f"could not read {path}")
            continue
        _check_config(path, content, floor, res)
    if not res.problems:
        res.ok(f"Vitest coverage gate enforces >= {floor}%")
    return res
