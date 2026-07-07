"""Repo paths for the meta-tests, anchored on zyplux's own pyproject.toml so nesting depth can't silently break them."""

import tomllib
from pathlib import Path


def find_zyplux_root() -> Path:
    for directory in Path(__file__).resolve().parents:
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            name = tomllib.loads(pyproject.read_text()).get("project", {}).get("name")
            if name != "zyplux":
                raise RuntimeError(f"nearest pyproject.toml names project '{name}', not 'zyplux': {pyproject}")
            return directory
    raise RuntimeError("zyplux pyproject.toml not found above the totchef meta-tests")


REPO_ROOT = find_zyplux_root()
SRC = REPO_ROOT / "apps" / "totchef" / "src"
TESTS = REPO_ROOT / "tests" / "totchef"
STORIES_DIR = TESTS / "stories"


def list_story_docs() -> list[Path]:
    return sorted(STORIES_DIR.glob("[0-9]*_*.md"), key=lambda path: int(path.name.split("_")[0]))
