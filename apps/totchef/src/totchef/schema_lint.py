"""Lint recipe.toml before chef runs it: every section resolves to a cook, the depends_on graph is acyclic, and every node's cook constructs from its slice (the same `build_cook` path a run takes)."""

import sys
from graphlib import CycleError, TopologicalSorter

from pydantic import ValidationError

from totchef.recipe_graph import (
    Node,
    build_cook,
    build_node_graph,
    build_nodes,
    load_cook_class,
)


def find_schema_problems(config: dict, nodes: dict[str, Node]) -> list[str]:
    """Validate each node by constructing its cook — the exact `build_cook` path a run takes, so lint never accepts a shape the run can't build — collecting every Pydantic error as a readable `[node] loc: message` line (empty == valid)."""
    problems: list[str] = []
    for node_id, node in nodes.items():
        try:
            build_cook(node, config)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(part) for part in err["loc"]) or "(entry)"
                problems.append(f"  [{node_id}] {loc}: {err['msg']}")
    return problems


def rule_sections_resolve_to_cooks(nodes: dict[str, Node]) -> None:
    """Every section names a cook module that imports to exactly one cook class (load_cook_class exits on a missing or ambiguous one)."""
    for section in {node.section for node in nodes.values()}:
        load_cook_class(section)


def rule_dependencies_acyclic(nodes: dict[str, Node]) -> None:
    """The depends_on graph resolves and topo-sorts (build_node_graph exits on an unknown or self dependency; a cycle would deadlock the schedule)."""
    try:
        list(TopologicalSorter(build_node_graph(nodes)).static_order())
    except CycleError as exc:
        sys.exit(f"ERROR: dependency cycle in recipe.toml: {' -> '.join(exc.args[1])}")


def rule_root_only_on_leaves(config: dict, nodes: dict[str, Node]) -> None:
    """needs_root must be granted per leaf, never on a subtable header — build_nodes folds a header's needs_root onto every entry, granting root wholesale."""
    sections: dict[str, list[Node]] = {}
    for node in nodes.values():
        sections.setdefault(node.section, []).append(node)
    offenders = sorted(
        section for section, entries in sections.items() if config[section].get("needs_root") and any(entry.entry is not None for entry in entries)
    )
    if offenders:
        named = ", ".join(f"[{section}]" for section in offenders)
        sys.exit(
            f"ERROR: needs_root enabled on subtable section header(s) {named}. "
            "Grant root per entry (a leaf), not on a whole section — move needs_root "
            "onto each entry that needs it (least privilege)."
        )


def rule_slices_match_schema(config: dict, nodes: dict[str, Node]) -> None:
    """Each node's cook constructs from its slice — the same validation `up` performs."""
    if problems := find_schema_problems(config, nodes):
        sys.exit("ERROR: recipe.toml schema validation failed:\n" + "\n".join(problems))


def validate(config: dict) -> None:
    nodes = build_nodes(config)
    rule_sections_resolve_to_cooks(nodes)
    rule_root_only_on_leaves(config, nodes)
    rule_dependencies_acyclic(nodes)
    rule_slices_match_schema(config, nodes)
