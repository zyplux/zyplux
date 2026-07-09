from __future__ import annotations

import re
import tomllib
from typing import TYPE_CHECKING

from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "line_length"
SUMMARY = "ruff line-length and prettier printWidth are both 120"
SCOPE = Scope.CONTENT

RUFF_PATH = "ruff.toml"

_PRETTIER_PATHS = (
    "prettier.config.ts",
    "prettier.config.js",
    "prettier.config.mjs",
    "prettier.config.cjs",
    ".prettierrc.ts",
    ".prettierrc.js",
    ".prettierrc.mjs",
    ".prettierrc.cjs",
    ".prettierrc.json",
    ".prettierrc.json5",
    ".prettierrc.yaml",
    ".prettierrc.yml",
    ".prettierrc",
)
_PRINT_WIDTH = re.compile(r"""['"]?printWidth['"]?\s*[:=]\s*(\d+)""")


def _ruff_width(content: str) -> int | None:
    try:
        config = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return None
    width = config.get("line-length")
    return width if isinstance(width, int) else None


def _prettier_width(content: str) -> int | None:
    match = _PRINT_WIDTH.search(content)
    return int(match.group(1)) if match else None


def _find_prettier(repo: Repo, ctx: Context) -> tuple[str, str] | None:
    for path in _PRETTIER_PATHS:
        content = ctx.file(repo, path)
        if content is not None:
            return path, content
    return None


def _check_width(path: str, setting: str, width: int | None, required: int, res: CheckResult) -> None:
    if width is None:
        res.fail(f"{path} does not set {setting} = {required}")
    elif width != required:
        res.fail(f"{path} sets {setting} = {width}, expected {required}")


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    required = ctx.config.line_width
    ruff = ctx.file(repo, RUFF_PATH)
    prettier = _find_prettier(repo, ctx)
    if ruff is None and prettier is None:
        res.skip("no ruff or prettier config")
        return res

    if ruff is not None:
        _check_width(RUFF_PATH, "line-length", _ruff_width(ruff), required, res)
    if prettier is not None:
        path, content = prettier
        _check_width(path, "printWidth", _prettier_width(content), required, res)

    if not res.problems:
        res.ok(f"ruff and prettier both wrap at {required}")
    return res
