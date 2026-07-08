"""Find the recipe and its asset dirs: `--recipe` wins, then `$TOTCHEF_RECIPE`, cwd, else the `totchef init` pin."""

import os
import sys
import tomllib
from pathlib import Path

RECIPE_NAMES = ("totchef.toml", "totchef_recipe.toml", "totchef-recipe.toml")
FILES_DIR_NAMES = ("totchef_files", "totchef-files")
COOKS_DIR_NAMES = ("totchef_cooks", "totchef-cooks")
RECIPE_ENV = "TOTCHEF_RECIPE"
CONFIG_NAME = "config.toml"


def config_home() -> Path:
    """The per-user config root, honoring XDG_CONFIG_HOME (default ~/.config)."""
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def config_path() -> Path:
    """Where `totchef init` pins the default recipe pointer."""
    return config_home() / "totchef" / CONFIG_NAME


def recipe_in_dir(directory: Path) -> Path | None:
    """The first recognized recipe filename present directly in `directory`."""
    for name in RECIPE_NAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _sibling_dir(recipe_path: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = recipe_path.parent / name
        if candidate.is_dir():
            return candidate
    return None


def find_files_dir(recipe_path: Path) -> Path:
    """The recipe's sibling assets dir: first existing of `totchef_files`/`totchef-files`, else primary name."""
    return _sibling_dir(recipe_path, FILES_DIR_NAMES) or recipe_path.parent / FILES_DIR_NAMES[0]


def find_cooks_dir(recipe_path: Path) -> Path | None:
    """The recipe's sibling custom-cooks dir (`totchef_cooks`/`totchef-cooks`), or None when it has none."""
    return _sibling_dir(recipe_path, COOKS_DIR_NAMES)


def resolve_explicit(explicit: Path, *, follow_symlinks: bool = True) -> Path:
    """An explicit `--recipe`/`totchef init` arg: a file, or dir holding one; symlinks=False keeps the given symlink."""
    if explicit.is_dir():
        found = recipe_in_dir(explicit)
        if found is None:
            sys.exit(f"ERROR: {explicit} is a directory with no {' / '.join(RECIPE_NAMES)}.")
        return found.resolve() if follow_symlinks else found.absolute()
    if not explicit.is_file():
        sys.exit(f"ERROR: {explicit} does not exist.")
    return explicit.resolve() if follow_symlinks else explicit.absolute()


def _cwd_chain() -> list[Path]:
    start = Path.cwd()
    return [start, *start.parents]


def _saved_recipe() -> Path | None:
    """The recipe a `totchef init` pinned, resolved past any symlink; None if unset, malformed, or gone."""
    config = config_path()
    if not config.is_file():
        return None
    try:
        saved = tomllib.loads(config.read_text()).get("recipe")
    except tomllib.TOMLDecodeError:
        return None
    if not isinstance(saved, str):
        return None
    pinned = Path(saved).expanduser()
    if pinned.is_dir():
        found = recipe_in_dir(pinned)
        return found.resolve() if found else None
    return pinned.resolve() if pinned.is_file() else None


def try_find_recipe() -> Path | None:
    """Resolve the recipe without an explicit flag, or None — used where a recipe is optional (e.g. `--list-cooks`)."""
    if env := os.environ.get(RECIPE_ENV):
        path = Path(env)
        if path.is_file():
            return path.resolve()
    for directory in _cwd_chain():
        if found := recipe_in_dir(directory):
            return found.resolve()
    return _saved_recipe()


def _not_found_message() -> str:
    names = " / ".join(RECIPE_NAMES)
    looked = "\n".join([
        *(f"  - {names} in {directory}" for directory in _cwd_chain()),
        f"  - a recipe pinned by `totchef init` ({config_path()})",
    ])
    return (
        f"ERROR: no totchef recipe found. Looked in:\n{looked}\n"
        "Write one (see the README), run `totchef init PATH`, or pass --recipe PATH."
    )


def find_recipe(explicit: Path | None = None) -> Path:
    """Resolve the recipe: explicit flag, $TOTCHEF_RECIPE, cwd name, or init pin; exit naming where it looked."""
    if explicit is not None:
        return resolve_explicit(explicit)
    if env := os.environ.get(RECIPE_ENV):
        path = Path(env)
        if not path.is_file():
            sys.exit(f"ERROR: {RECIPE_ENV}={env} does not exist.")
        return path.resolve()
    for directory in _cwd_chain():
        if found := recipe_in_dir(directory):
            return found.resolve()
    if saved := _saved_recipe():
        return saved
    sys.exit(_not_found_message())


def _toml_basic_string(value: str) -> str:
    """Quote a path as a TOML basic string, escaping the two characters that would otherwise break it."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def save_recipe(recipe_path: Path) -> Path:
    """Pin `recipe_path` as the default recipe so `totchef up` finds it anywhere; returns the config file."""
    config = config_path()
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(f"recipe = {_toml_basic_string(str(recipe_path))}\n")
    return config
