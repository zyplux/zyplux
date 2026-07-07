"""Resolve a recipe section to its cook class: built-in and third-party cooks register through the `totchef.cooks` entry-point group; loose `*_cook.py` files under the recipe's sibling totchef_cooks/ (the primary extension point) or the user config dir (a prototyping hatch) shadow them, so a recipe repo carries its own highly custom cooks."""

import importlib.util
import os
import sys
from dataclasses import dataclass
from functools import cache
from importlib.metadata import entry_points
from pathlib import Path

from totchef.cook_base import CookBase

COOK_GROUP = "totchef.cooks"
COOK_SUFFIXES = ("_root_cook", "_cook")

_recipe_cooks_dir: Path | None = None


def set_recipe_cooks_dir(path: Path | None) -> None:
    """Pin the recipe's sibling custom-cooks dir (totchef_cooks/) so its loose `*_cook.py` plugins resolve alongside the built-ins; None clears it (between tests). Clears the registry cache so the change takes effect."""
    global _recipe_cooks_dir
    _recipe_cooks_dir = path
    cook_registry.cache_clear()


def config_cooks_dir() -> Path:
    """The user config dir scanned for loose `<section>_cook.py` plugins, honoring XDG_CONFIG_HOME — a prototyping hatch beside the recipe-relative totchef_cooks/."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "totchef" / "cooks"


@dataclass(frozen=True)
class CookEntry:
    """One resolved cook: which section it serves, the class, where it came from, and whether it runs as root."""

    section: str
    cook: type[CookBase]
    origin: str

    @property
    def needs_root(self) -> bool:
        return self.cook.needs_root


def _as_cook_class(obj: object, where: str) -> type[CookBase]:
    if not (isinstance(obj, type) and issubclass(obj, CookBase)):
        sys.exit(f"ERROR: {where} is not a CookBase subclass.")
    return obj


def _entry_point_cooks() -> dict[str, CookEntry]:
    cooks: dict[str, CookEntry] = {}
    for ep in entry_points(group=COOK_GROUP):
        dist = ep.dist.name if ep.dist else "?"
        origin = "built-in" if dist == "totchef" else f"plugin:{dist}"
        cooks[ep.name] = CookEntry(ep.name, _as_cook_class(ep.load(), f"entry point {ep.name} = {ep.value}"), origin)
    return cooks


def _load_file_cook(path: Path) -> type[CookBase]:
    spec = importlib.util.spec_from_file_location(f"totchef._local_cooks.{path.stem}", path)
    if spec is None or spec.loader is None:
        sys.exit(f"ERROR: could not load cook from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    classes = [obj for obj in vars(module).values() if isinstance(obj, type) and issubclass(obj, CookBase) and obj.__module__ == spec.name]
    if len(classes) != 1:
        sys.exit(f"ERROR: {path} must define exactly one cook class, found {len(classes)}: {[c.__name__ for c in classes]}.")
    return classes[0]


def _dir_cooks(cooks_dir: Path | None) -> dict[str, CookEntry]:
    cooks: dict[str, CookEntry] = {}
    if cooks_dir is None or not cooks_dir.is_dir():
        return cooks
    for path in sorted(cooks_dir.glob("*_cook.py")):
        section = next((path.stem[: -len(suffix)] for suffix in COOK_SUFFIXES if path.stem.endswith(suffix)), path.stem)
        cooks[section] = CookEntry(section, _load_file_cook(path), f"local:{path}")
    return cooks


@cache
def cook_registry() -> dict[str, CookEntry]:
    """Every available cook keyed by section — entry points first, then the user config dir, then the recipe's totchef_cooks/ shadowing both, so a recipe-local cook (or a prototype) overrides a built-in."""
    return {**_entry_point_cooks(), **_dir_cooks(config_cooks_dir()), **_dir_cooks(_recipe_cooks_dir)}


def load_cook_class(section: str) -> type[CookBase]:
    """The cook class serving a recipe section, or a clear exit naming the section and where cooks are looked for."""
    registry = cook_registry()
    entry = registry.get(section)
    if entry is None:
        known = ", ".join(sorted(registry)) or "none"
        sys.exit(
            f"ERROR: [{section}] -> no cook registered for this section. Known sections: {known}. Add a plugin or drop a {section}_cook.py in {config_cooks_dir()}."
        )
    return entry.cook
