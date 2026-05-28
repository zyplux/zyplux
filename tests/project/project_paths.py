"""Repo paths for the meta-tests, anchored on the totchef pyproject.toml so nesting depth can't silently break them."""

import tomllib
from pathlib import Path


def find_repo_root() -> Path:
    for directory in Path(__file__).resolve().parents:
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            name = tomllib.loads(pyproject.read_text()).get("project", {}).get("name")
            if name != "totchef":
                raise RuntimeError(f"nearest pyproject.toml names project '{name}', not 'totchef': {pyproject}")
            return directory
    raise RuntimeError("totchef pyproject.toml not found above the meta-tests")


REPO_ROOT = find_repo_root()
SRC = REPO_ROOT / "src"
TESTS = REPO_ROOT / "tests"
STORIES_DIR = REPO_ROOT / "tests" / "stories"
STORIES_DOC = STORIES_DIR / "user-stories.md"
