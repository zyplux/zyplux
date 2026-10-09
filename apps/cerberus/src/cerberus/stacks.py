from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

type Language = Literal["python", "javascript"]

SOURCE_SUFFIXES: dict[Language, frozenset[str]] = {
    "python": frozenset({".py", ".pyi"}),
    "javascript": frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}),
}
TOOL_LANGUAGES: dict[str, Language] = {
    "vulture": "python",
    "ruff": "python",
    "pyrefly": "python",
    "pytest": "python",
    "knip": "javascript",
    "typecheck": "javascript",
    "lint": "javascript",
    "lint:fix": "javascript",
    "test": "javascript",
}


def has_source(repo: Repo, ctx: Context, language: Language) -> bool:
    return any(PurePosixPath(path).suffix in SOURCE_SUFFIXES[language] for path in ctx.paths(repo))


def can_run_command(repo: Repo, ctx: Context, args: tuple[str, ...]) -> bool:
    tool = args[2] if args[:2] in {("uv", "run"), ("pnpm", "run")} else args[0]
    language = TOOL_LANGUAGES.get(tool)
    return language is None or has_source(repo, ctx, language)
