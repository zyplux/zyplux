import shutil

import pytest
from cerberus import justfile

pytestmark = pytest.mark.skipif(
    shutil.which("just") is None, reason="requires the `just` binary on PATH"
)

WITH_INTERPOLATION = """
recipe := "examples/recipe.toml"

default:
    @just --list

install:
    uv sync

test:
    uv run pytest

up *args:
    uv run totchef up --recipe {{ recipe }} {{ args }}

check: install test
"""


def test_parse_extracts_recipes_aliases_and_deps():
    jf = justfile.parse(
        "alias c := check\n"
        "default:\n    @just --list\n"
        "install:\n    bun install\n"
        "check: install test\n"
        "test:\n    bun test\n"
    )
    assert jf.aliases == {"c": "check"}
    assert jf.recipes["check"] == ["install", "test"]
    assert "just --list" in jf.bodies["default"]


def test_parse_survives_interpolation_in_bodies():
    # Regression: interpolation fragments are nested lists, not strings.
    jf = justfile.parse(WITH_INTERPOLATION)
    assert jf.recipes["check"] == ["install", "test"]
    assert "uv run totchef up" in jf.bodies["up"]


def test_is_subsequence():
    assert justfile.is_subsequence(["a", "c"], ["a", "b", "c"])
    assert justfile.is_subsequence(
        ["install", "knip", "test"], ["install", "build", "knip", "test"]
    )
    assert not justfile.is_subsequence(["c", "a"], ["a", "b", "c"])
    assert not justfile.is_subsequence(["x"], ["a", "b"])
