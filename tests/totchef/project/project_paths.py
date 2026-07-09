"""Repo paths for the meta-tests, anchored on zyplux's own pyproject.toml so nesting depth can't silently break them."""

import tomllib
from pathlib import Path


class WrongProjectRootError(RuntimeError):
    def __init__(self, pyproject: Path, name: str | None) -> None:
        super().__init__(f"nearest pyproject.toml names project '{name}', not 'zyplux': {pyproject}")


class ZypluxRootNotFoundError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("zyplux pyproject.toml not found above the totchef meta-tests")


def find_zyplux_root() -> Path:
    for directory in Path(__file__).resolve().parents:
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            name = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {}).get("name")
            if name != "zyplux":
                raise WrongProjectRootError(pyproject, name)
            return directory
    raise ZypluxRootNotFoundError


REPO_ROOT = find_zyplux_root()
SRC = REPO_ROOT / "apps" / "totchef" / "src"
TESTS = REPO_ROOT / "tests" / "totchef"
STORIES_DIR = TESTS / "stories"
