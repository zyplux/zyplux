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


def _from_dict(data: dict[str, Any]) -> Config:
    aliases = data.get("aliases", {})
    recipes = data.get("recipes", {})
    ci = data.get("ci", {})
    ci_required = ci.get("required", {})
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
    )


def load(path: Path | None = None) -> Config:
    if path is not None:
        return _from_dict(tomllib.loads(path.read_text()))
    bundled = resources.files("cerberus").joinpath("cerberus.toml").read_text()
    return _from_dict(tomllib.loads(bundled))


def repo_disabled_checks(root: Path) -> frozenset[str]:
    """Check ids the repo opts out of, via `[tool.cerberus] disable` in pyproject.toml."""
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return frozenset()
    tool = tomllib.loads(pyproject.read_text()).get("tool", {})
    cerberus: Any = tool.get("cerberus", {}) if isinstance(tool, dict) else {}
    disabled = cerberus.get("disable", []) if isinstance(cerberus, dict) else cerberus
    if not isinstance(disabled, list) or not all(isinstance(check, str) for check in disabled):
        msg = "[tool.cerberus] disable must be a list of check id strings"
        raise TypeError(msg)
    return frozenset(disabled)
