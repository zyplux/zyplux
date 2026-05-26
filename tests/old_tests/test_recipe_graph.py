import pytest

from totchef.recipe_graph import build_node_graph, build_nodes


def graph_for(config: dict) -> dict[str, set[str]]:
    return build_node_graph(build_nodes(config))


# --- build_nodes: meta-key precedence (entry -> section -> cook-class default) ---


def test_entry_meta_overrides_section_meta():
    config = {
        "apt_repo": {
            "needs_root": True,
            "depends_on": ["url.rustup"],
            "brave": {"needs_root": False, "depends_on": ["apt_pkg"]},
        }
    }
    brave = build_nodes(config)["apt_repo.brave"]
    assert brave.needs_root is False
    assert brave.depends_on == ("apt_pkg",)


def test_entry_inherits_section_meta_when_absent():
    config = {
        "apt_repo": {
            "needs_root": True,
            "depends_on": ["url.rustup"],
            "code": {},
        }
    }
    code = build_nodes(config)["apt_repo.code"]
    assert code.needs_root is True
    assert code.depends_on == ("url.rustup",)


def test_section_falls_back_to_cook_class_needs_root():
    # No needs_root anywhere -> chef reads the cook class: apt_pkg is always-root,
    # cargo is not. This is the only branch that imports a real cook.
    assert build_nodes({"apt_pkg": {"packages": ["vim"]}})["apt_pkg"].needs_root is True
    assert build_nodes({"cargo": {"packages": []}})["cargo"].needs_root is False


def test_plain_section_is_one_node_with_no_entry():
    node = build_nodes({"apt_pkg": {"needs_root": True, "packages": ["vim"]}})["apt_pkg"]
    assert node.section == "apt_pkg"
    assert node.entry is None


# --- build_node_graph: dependency resolution + whole-section fan-out ---


def test_section_dependency_fans_out_to_every_entry():
    config = {
        "apt_repo": {"needs_root": True, "brave": {}, "vscode": {}},
        "apt_pkg": {"needs_root": True, "depends_on": ["apt_repo"], "packages": []},
    }
    assert graph_for(config)["apt_pkg"] == {"apt_repo.brave", "apt_repo.vscode"}


def test_section_fanout_excludes_self_no_self_loop():
    # An entry waiting on its own section means "after my siblings", never itself.
    config = {
        "apt_repo": {
            "needs_root": True,
            "brave": {"depends_on": ["apt_repo"]},
            "vscode": {},
        }
    }
    assert graph_for(config)["apt_repo.brave"] == {"apt_repo.vscode"}


def test_unknown_dependency_exits():
    config = {"apt_pkg": {"needs_root": True, "depends_on": ["nope"], "packages": []}}
    with pytest.raises(SystemExit, match="neither a node nor a section"):
        graph_for(config)


@pytest.mark.parametrize(
    "config",
    [
        {"apt_pkg": {"needs_root": True, "depends_on": ["apt_pkg"], "packages": []}},
        {"apt_repo": {"needs_root": True, "brave": {"depends_on": ["apt_repo.brave"]}}},
    ],
)
def test_direct_self_dependency_exits(config):
    with pytest.raises(SystemExit, match="depends_on itself"):
        graph_for(config)
