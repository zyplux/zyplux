import tomllib
from pathlib import Path

import pytest

from totchef.recipe_graph import merge_section_defaults

FIXTURE_RECIPE = Path(__file__).parent / "fixtures" / "recipe.toml"


@pytest.fixture
def section() -> dict:
    """A subtable section with list and scalar defaults, the two meta keys, and three entries exercising union, override, and pure inheritance."""
    return {
        "needs_root": True,
        "depends_on": ["apt_pkg"],
        "features": ["base_a", "base_b"],
        "channel": "stable",
        "brave": {"features": ["base_b", "extra_c"], "channel": "beta"},
        "code": {"argv_json": ".vscode/argv.json"},
        "empty": {},
    }


def test_list_default_unions_with_entry_section_order_first(section):
    assert merge_section_defaults(section, "brave")["features"] == [
        "base_a",
        "base_b",
        "extra_c",
    ]


def test_union_dedupes_overlap(section):
    features = merge_section_defaults(section, "brave")["features"]
    assert features.count("base_b") == 1


def test_scalar_entry_overrides_section_default(section):
    assert merge_section_defaults(section, "brave")["channel"] == "beta"


@pytest.mark.parametrize("entry", ["code", "empty"])
def test_entry_inherits_defaults_when_key_absent(section, entry):
    slice_ = merge_section_defaults(section, entry)
    assert slice_["features"] == ["base_a", "base_b"]
    assert slice_["channel"] == "stable"


def test_inherited_list_is_a_fresh_copy(section):
    """Mutating one entry's merged list must not bleed into the shared default or another entry — the union builds a new list, not an alias."""
    merge_section_defaults(section, "code")["features"].append("leak")
    assert section["features"] == ["base_a", "base_b"]
    assert merge_section_defaults(section, "empty")["features"] == ["base_a", "base_b"]


def test_meta_keys_never_reach_the_slice(section):
    slice_ = merge_section_defaults(section, "brave")
    assert "needs_root" not in slice_
    assert "depends_on" not in slice_


def test_sibling_subtables_are_not_defaults(section):
    slice_ = merge_section_defaults(section, "code")
    assert "brave" not in slice_
    assert "empty" not in slice_


def test_empty_entry_gets_exactly_the_scalar_defaults(section):
    assert merge_section_defaults(section, "empty") == {
        "features": ["base_a", "base_b"],
        "channel": "stable",
    }


def test_scalar_entry_overriding_a_list_default_wins_without_splatting():
    section = {"features": ["base_a"], "odd": {"features": "single"}}
    assert merge_section_defaults(section, "odd")["features"] == "single"


@pytest.fixture(scope="session")
def fixture_recipe() -> dict:
    return tomllib.loads(FIXTURE_RECIPE.read_text())


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ("extender", ["BaseOne", "BaseTwo", "ExtraOne", "ExtraTwo"]),
        ("inheritor", ["BaseOne", "BaseTwo"]),
        ("overlap", ["BaseOne", "BaseTwo", "ExtraThree"]),
    ],
)
def test_parsed_toml_entries_resolve_to_expected_features(fixture_recipe, entry, expected):
    assert merge_section_defaults(fixture_recipe["gpu_apps"], entry)["features"] == expected
