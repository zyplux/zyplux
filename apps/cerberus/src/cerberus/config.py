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
    """Build a Config from per-bite tables: every setting lives under `[<bite id>]`."""
    justfile = _table(data, "justfile_baseline")
    required = justfile.get("required", [])
    recommended = justfile.get("recommended", [])
    toolchain = _table(data, "workflow_toolchain_only")
    ci = _table(data, "ci_check_sequence")
    ci_required = _table(ci, "required")
    jscpd_dupes = _table(data, "jscpd_dupes_threshold")
    return Config(
        default_recipe_marker=justfile["default_recipe_marker"],
        required_aliases=_aliases(required),
        recommended_aliases=_aliases(recommended),
        required_recipes=_recipes(required),
        recommended_recipes=_recipes(recommended),
        check_pipeline=tuple(justfile.get("check_pipeline", [])),
        wrapped_tools=tuple(justfile.get("wrapped_tools", [])),
        allowed_setup_actions=tuple(toolchain.get("allowed_setup_actions", [])),
        ci_image=ci.get("image", ""),
        ci_required_ts=tuple(ci_required.get("ts", [])),
        ci_required_python=tuple(ci_required.get("python", [])),
        jscpd_dupes_threshold=jscpd_dupes.get("threshold", 0.1),
        jscpd_dupes_pattern=jscpd_dupes.get("pattern", "**/*.{ts,tsx,py}"),
        jscpd_dupes_ignore=tuple(jscpd_dupes.get("ignore", ["**/dist/**", "**/.venv/**", "**/*.gen.*"])),
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
    if path is not None:
        return _from_dict(tomllib.loads(path.read_text()))
    data = tomllib.loads(resources.files("cerberus").joinpath("cerberus.toml").read_text())
    repo_toml = repo_root / "cerberus.toml" if repo_root is not None else None
    if repo_toml is not None and repo_toml.is_file():
        data = _overlay(data, tomllib.loads(repo_toml.read_text()))
    return _from_dict(data)
