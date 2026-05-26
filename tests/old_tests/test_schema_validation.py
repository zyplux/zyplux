import pytest

from totchef.recipe_graph import build_nodes
from totchef.schema_lint import find_schema_problems


def problems_for(config: dict) -> list[str]:
    return find_schema_problems(config, build_nodes(config))


def test_valid_minimal_recipe_has_no_problems():
    config = {
        "desktop": {"brave": {"desktop": "/usr/share/applications/brave.desktop"}},
        "apt_pkg": {"packages": ["vim", "git"]},
    }
    assert problems_for(config) == []


def test_unsupported_key_is_rejected():
    config = {"desktop": {"brave": {"desktop": "/x.desktop", "featuers": ["Vaapi"]}}}
    problems = problems_for(config)
    assert any("featuers" in p for p in problems)


def test_unsupported_key_names_the_node():
    config = {"desktop": {"brave": {"desktop": "/x.desktop", "bogus": 1}}}
    assert any("[desktop.brave]" in p for p in problems_for(config))


def test_missing_required_key_is_rejected():
    config = {"desktop": {"brave": {"features": ["Vaapi"]}}}  # no `desktop`
    assert any("desktop" in p for p in problems_for(config))


def test_wrong_type_is_rejected():
    config = {"apt_pkg": {"packages": "vim"}}  # a string, not a list
    assert problems_for(config) != []


@pytest.mark.parametrize(
    "entry",
    [
        {},  # neither local_state nor argv_json
        {"local_state": "Local State", "argv_json": "argv.json"},  # both
    ],
)
def test_chromium_flags_requires_exactly_one_target(entry):
    config = {"chromium_flags": {"brave": entry}}
    assert any("exactly one" in p for p in problems_for(config))


def test_file_requires_exactly_one_body():
    config = {"file": {"x": {"path": "/tmp/x", "source": "s", "content": "c"}}}
    assert any("exactly one" in p for p in problems_for(config))


def test_section_default_is_folded_before_validation():
    # A section-level `features` list must reach the entry's model as a known key,
    # not trip the unsupported-key check.
    config = {"desktop": {"features": ["Vaapi"], "brave": {"desktop": "/x.desktop"}}}
    assert problems_for(config) == []


def test_hook_on_versioned_section_is_rejected():
    # pre_hook/post_hook live on StateEntrySpec, not the versioned package schema,
    # so a hook on a package section is an unknown key — fail loud at lint time
    # rather than be a silent no-op (run_versioned never runs hooks).
    config = {"apt_pkg": {"packages": ["vim"], "post_hook": "echo done"}}
    assert any("post_hook" in p for p in problems_for(config))


def test_hook_on_state_entry_is_accepted():
    config = {"file": {"shim": {"path": "/tmp/x", "content": "c", "post_hook": "echo done"}}}
    assert problems_for(config) == []
