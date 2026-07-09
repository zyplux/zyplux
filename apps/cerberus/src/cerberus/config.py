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
    jscpd_dupes_threshold: float
    jscpd_dupes_pattern: str
    jscpd_dupes_ignore: tuple[str, ...]


def _table(data: dict[str, Any], key: str) -> dict[str, Any]:
    section = data.get(key, {})
    if not isinstance(section, dict):
        msg = f"cerberus.toml [{key}] must be a table, got {type(section).__name__}"
        raise TypeError(msg)
    return section


def _from_dict(data: dict[str, Any]) -> Config:
    aliases = _table(data, "aliases")
    recipes = _table(data, "recipes")
    ci = _table(data, "ci")
    ci_required = _table(ci, "required")
    jscpd_dupes = _table(data, "jscpd_dupes_threshold")
    return Config(
        default_recipe_marker=data["default_recipe_marker"],
        required_aliases=dict(aliases.get("required", {})),
        recommended_aliases=dict(aliases.get("recommended", {})),
        required_recipes=tuple(recipes.get("required", [])),
        recommended_recipes=tuple(recipes.get("recommended", [])),
        check_pipeline=tuple(recipes.get("check_pipeline", [])),
        wrapped_tools=tuple(recipes.get("wrapped_tools", [])),
        allowed_setup_actions=tuple(ci.get("allowed_setup_actions", [])),
        ci_image=ci.get("image", ""),
        ci_required_ts=tuple(ci_required.get("ts", [])),
        ci_required_python=tuple(ci_required.get("python", [])),
        jscpd_dupes_threshold=jscpd_dupes.get("threshold", 0.1),
        jscpd_dupes_pattern=jscpd_dupes.get("pattern", "**/*.{ts,tsx,py}"),
        jscpd_dupes_ignore=tuple(jscpd_dupes.get("ignore", ["**/dist/**", "**/.venv/**", "**/*.gen.*"])),
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
    if path is not None:
        return _from_dict(tomllib.loads(path.read_text()))
    data = tomllib.loads(resources.files("cerberus").joinpath("cerberus.toml").read_text())
    repo_toml = repo_root / "cerberus.toml" if repo_root is not None else None
    if repo_toml is not None and repo_toml.is_file():
        data = _overlay(data, tomllib.loads(repo_toml.read_text()))
    return _from_dict(data)


def repo_disabled_checks(root: Path) -> frozenset[str]:
    """Check ids the repo opts out of, via `[tool.cerberus] disable` in pyproject.toml."""
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return frozenset()
    tool = tomllib.loads(pyproject.read_text()).get("tool", {})
    cerberus: Any = tool.get("cerberus", {}) if isinstance(tool, dict) else {}
    disabled = cerberus.get("disable", []) if isinstance(cerberus, dict) else cerberus
    if not isinstance(disabled, list) or not all(isinstance(check, str) for check in disabled):
        msg = "[tool.cerberus] disable must be a list of bite id strings"
        raise TypeError(msg)
    return frozenset(disabled)
