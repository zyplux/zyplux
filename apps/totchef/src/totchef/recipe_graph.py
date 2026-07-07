"""Recipe -> scheduling graph: turn recipe.toml into a DAG of Nodes and construct each node's cook (section -> cook-class resolution lives in registry, graph validation in schema_lint)."""

import sys
from dataclasses import dataclass

from totchef.cook_base import CookBase
from totchef.recipe_types import RecipeConfig, RecipeValue
from totchef.registry import load_cook_class

# Keys chef reads off a slice, then strips before handing it to the cook.
META_KEYS = ("needs_root", "depends_on")


def strip_meta(slice_: RecipeConfig) -> RecipeConfig:
    return {k: v for k, v in slice_.items() if k not in META_KEYS}


def merge_section_defaults(section_data: RecipeConfig, entry: str) -> RecipeConfig:
    """Fold a subtable section's own scalar/list keys into an entry's slice as defaults: lists union (entry extends), everything else the entry overrides."""
    defaults = {k: v for k, v in section_data.items() if k not in META_KEYS and not isinstance(v, dict)}
    entry_value = section_data[entry]
    assert isinstance(entry_value, dict)  # build_nodes only names entries whose value passed this same isinstance check
    entry_data = strip_meta(entry_value)
    merged = {**defaults, **entry_data}
    for key, shared in defaults.items():
        if not isinstance(shared, list):
            continue
        extra = entry_data.get(key)
        if isinstance(extra, list):
            merged[key] = list(dict.fromkeys([*shared, *extra]))
        elif key not in entry_data:
            merged[key] = list(shared)
    return merged


@dataclass(frozen=True)
class Node:
    """One unit of work chef schedules — one entry of a subtable section, or a whole plain-data/empty section."""

    id: str
    section: str
    entry: str | None
    needs_root: bool
    depends_on: tuple[str, ...]


def _str_list(value: RecipeValue | None, default: list[str]) -> list[str]:
    """A `depends_on` value coerced to the list of strings it always is by schema, falling back only when the key itself is absent (an explicit empty list is a real, distinct choice, not a fallback trigger)."""
    if value is None:
        return default
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else default


def _bool(value: RecipeValue | None, default: bool) -> bool:
    """A `needs_root` value coerced to the bool it always is by schema, same rationale as `_str_list`."""
    return value if isinstance(value, bool) else default


def build_nodes(config: RecipeConfig) -> dict[str, Node]:
    nodes: dict[str, Node] = {}
    for section, data in config.items():
        assert isinstance(data, dict)  # every top-level recipe key is a TOML table (a section)
        sec_root = _bool(data.get("needs_root"), load_cook_class(section).needs_root)
        sec_deps = _str_list(data.get("depends_on"), [])
        children = {k: v for k, v in data.items() if k not in META_KEYS and isinstance(v, dict)}
        if children:
            for entry, entry_data in children.items():
                node_id = f"{section}.{entry}"
                nodes[node_id] = Node(
                    node_id,
                    section,
                    entry,
                    _bool(entry_data.get("needs_root"), sec_root),
                    tuple(_str_list(entry_data.get("depends_on"), sec_deps)),
                )
        else:
            nodes[section] = Node(section, section, None, sec_root, tuple(sec_deps))
    return nodes


def build_node_graph(nodes: dict[str, Node]) -> dict[str, set[str]]:
    """Resolve each node's `depends_on` to node ids: a dependency names an entry, a single-node section, or a whole section (fanning out to all its nodes)."""
    section_nodes: dict[str, set[str]] = {}
    for node_id, node in nodes.items():
        section_nodes.setdefault(node.section, set()).add(node_id)

    graph: dict[str, set[str]] = {}
    for node_id, node in nodes.items():
        deps: set[str] = set()
        for dep in node.depends_on:
            if dep == node_id:
                sys.exit(
                    f"ERROR: [{node_id}] depends_on itself ('{dep}'). A node can't "
                    "wait on its own completion — drop the self-reference. To wait "
                    "on the rest of your section, name the section, not this node."
                )
            if dep in nodes:
                deps.add(dep)
            elif dep in section_nodes:
                deps.update(section_nodes[dep])
            else:
                sys.exit(
                    f"ERROR: [{node_id}] depends_on '{dep}', which is neither a "
                    "node nor a section. Name an entry (e.g. 'bash.apt_prereqs'), "
                    "a single-node section (e.g. 'apt_pkg'), or a whole section to "
                    "fan out to all its entries (e.g. 'apt_repo')."
                )
        deps.discard(node_id)
        graph[node_id] = deps
    return graph


def node_slice(config: RecipeConfig, node: Node) -> RecipeConfig:
    """The dict a node's cook receives: an entry node gets its merged slice, a single-node section gets the section itself."""
    section_data = config[node.section]
    assert isinstance(section_data, dict)  # every top-level recipe key is a TOML table (a section)
    if node.entry is not None:
        return merge_section_defaults(section_data, node.entry)
    return strip_meta(section_data)


def build_cook(node: Node, config: RecipeConfig) -> CookBase:
    """Construct a node's cook from its recipe slice (validation only, no side effects): an entry-keyed cook receives `{entry: slice}`, any other consumes the slice flat — both lint and the runner construct through here, so lint can never accept a shape a run can't build."""
    cook_class = load_cook_class(node.section)
    slice_ = node_slice(config, node)
    if cook_class.entry_keyed and node.entry is not None:
        return cook_class({node.entry: slice_})
    return cook_class(slice_)
