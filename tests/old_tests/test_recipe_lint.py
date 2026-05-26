import pytest

from totchef.recipe_graph import build_nodes
from totchef.schema_lint import (
    rule_dependencies_acyclic,
    rule_root_only_on_leaves,
    rule_sections_resolve_to_cooks,
    rule_slices_match_schema,
)

# Each rule gets a happy case (returns, no exit) and a sad case (sys.exit). A rule
# that needs no cook uses a synthetic section with an explicit needs_root so
# build_nodes never imports one; the rest use real sections (apt_pkg, apt_repo).


# --- rule_sections_resolve_to_cooks ---


def test_known_section_resolves_to_a_cook():
    rule_sections_resolve_to_cooks(build_nodes({"apt_pkg": {"packages": ["vim"]}}))


def test_unknown_section_has_no_cook():
    config = {"made_up": {"needs_root": True, "packages": []}}
    with pytest.raises(SystemExit, match="no cook registered"):
        rule_sections_resolve_to_cooks(build_nodes(config))


# --- rule_root_only_on_leaves ---


def test_root_on_entry_leaf_is_allowed():
    config = {"apt_repo": {"brave": {"needs_root": True}, "vscode": {}}}
    rule_root_only_on_leaves(config, build_nodes(config))


def test_root_on_subtable_header_is_rejected():
    config = {"apt_repo": {"needs_root": True, "brave": {}, "vscode": {}}}
    with pytest.raises(SystemExit, match=r"subtable section header.*\[apt_repo\]"):
        rule_root_only_on_leaves(config, build_nodes(config))


# --- rule_dependencies_acyclic ---


def test_acyclic_graph_passes():
    config = {
        "bash": {
            "needs_root": False,
            "first": {},
            "second": {"depends_on": ["bash.first"]},
        }
    }
    rule_dependencies_acyclic(build_nodes(config))


def test_dependency_cycle_is_rejected():
    config = {
        "bash": {
            "needs_root": False,
            "first": {"depends_on": ["bash.second"]},
            "second": {"depends_on": ["bash.first"]},
        }
    }
    with pytest.raises(SystemExit, match="dependency cycle"):
        rule_dependencies_acyclic(build_nodes(config))


# --- rule_slices_match_schema ---


def test_valid_slice_passes():
    config = {"apt_pkg": {"packages": ["vim", "git"]}}
    rule_slices_match_schema(config, build_nodes(config))


def test_invalid_slice_is_rejected():
    config = {"apt_pkg": {"packages": "vim"}}  # a string, not a list
    with pytest.raises(SystemExit, match="schema validation failed"):
        rule_slices_match_schema(config, build_nodes(config))
