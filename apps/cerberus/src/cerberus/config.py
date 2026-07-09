from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib import resources
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class Config:
    default_recipe_marker: str
    required_aliases: dict[str, str]
    recommended_aliases: dict[str, str]
    required_recipes: tuple[str, ...]
    recommended_recipes: tuple[str, ...]
    check_pipeline: tuple[str, ...]
    wrapped_tools: tuple[str, ...]
    allowed_setup_actions: tuple[str, ...]
    ci_image: str
    ci_required_ts: tuple[str, ...]
    ci_required_python: tuple[str, ...]
    pyrefly_error_kinds: frozenset[str]
    ruff_sanctioned_ignore: frozenset[str]
    ruff_sanctioned_test_ignore: frozenset[str]
    line_width: int
    rumdl_canonical: str
    knip_required_ignore_workspaces: list[str]
    knip_prod_allowed_exclude: list[str]
    knip_allowed_customizations: dict[str, frozenset[str]]
    pytest_min_coverage: int
    vitest_min_coverage: int
    jscpd_threshold: float
    jscpd_pattern: str
    jscpd_ignore: tuple[str, ...]
    disabled_bites: frozenset[str]


def _table(data: dict[str, Any], key: str) -> dict[str, Any]:
    section = data.get(key, {})
    if not isinstance(section, dict):
        msg = f"cerberus.toml [{key}] must be a table, got {type(section).__name__}"
        raise TypeError(msg)
    return section


def _disabled_bites(data: dict[str, Any]) -> frozenset[str]:
    return frozenset(
        bite_id for bite_id, section in data.items() if isinstance(section, dict) and section.get("off") is True
    )


def _aliases(entries: list[dict[str, str]]) -> dict[str, str]:
    return {entry["alias"]: entry["recipe"] for entry in entries if "alias" in entry}


def _recipes(entries: list[dict[str, str]]) -> tuple[str, ...]:
    return tuple(entry["recipe"] for entry in entries)


def _from_dict(data: dict[str, Any]) -> Config:
    """Build a Config from per-bite tables: every setting lives under `[<bite id>]`.

    Strict on purpose: every key is required, so the bundled cerberus.toml is
    the single home of every default and a missing key fails loudly instead of
    falling back to a shadow value in code.
    """
    justfile = _table(data, "justfile")
    required = justfile["required"]
    recommended = justfile["recommended"]
    ci = _table(data, "ci_check_sequence")
    ruff = _table(data, "ruff")
    knip = _table(data, "knip")
    jscpd = _table(data, "jscpd")
    return Config(
        default_recipe_marker=justfile["default_recipe_marker"],
        required_aliases=_aliases(required),
        recommended_aliases=_aliases(recommended),
        required_recipes=_recipes(required),
        recommended_recipes=_recipes(recommended),
        check_pipeline=tuple(justfile["check_pipeline"]),
        wrapped_tools=tuple(justfile["wrapped_tools"]),
        allowed_setup_actions=tuple(_table(data, "workflow_toolchain_only")["allowed_setup_actions"]),
        ci_image=ci["image"],
        ci_required_ts=tuple(_table(ci, "required")["ts"]),
        ci_required_python=tuple(_table(ci, "required")["python"]),
        pyrefly_error_kinds=frozenset(_table(data, "pyrefly")["error_kinds"]),
        ruff_sanctioned_ignore=frozenset(ruff["sanctioned_ignore"]),
        ruff_sanctioned_test_ignore=frozenset(ruff["sanctioned_test_ignore"]),
        line_width=_table(data, "line_length")["width"],
        rumdl_canonical=_table(data, "rumdl")["canonical"],
        knip_required_ignore_workspaces=list(knip["required_ignore_workspaces"]),
        knip_prod_allowed_exclude=list(knip["prod_allowed_exclude"]),
        knip_allowed_customizations={
            key: frozenset(names) for key, names in _table(knip, "allowed_customizations").items()
        },
        pytest_min_coverage=_table(data, "pytest")["min_coverage"],
        vitest_min_coverage=_table(data, "vitest")["min_coverage"],
        jscpd_threshold=jscpd["threshold"],
        jscpd_pattern=jscpd["pattern"],
        jscpd_ignore=tuple(jscpd["ignore"]),
        disabled_bites=_disabled_bites(data),
    )


def _overlay(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _overlay(merged[key], value)
        else:
            merged[key] = value
    return merged


def load(path: Path | None = None, repo_root: Path | None = None) -> Config:
    """The bundled defaults with exactly one overlay applied on top.

    The overlay is the repo-root cerberus.toml, or the explicit `path` standing
    in for it; either names only what it overrides, key by key.
    """
    data = tomllib.loads(resources.files("cerberus").joinpath("cerberus.toml").read_text())
    if path is not None:
        return _from_dict(_overlay(data, tomllib.loads(path.read_text())))
    repo_toml = repo_root / "cerberus.toml" if repo_root is not None else None
    if repo_toml is not None and repo_toml.is_file():
        data = _overlay(data, tomllib.loads(repo_toml.read_text()))
    return _from_dict(data)
