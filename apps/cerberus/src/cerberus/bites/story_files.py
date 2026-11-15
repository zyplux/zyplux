from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

FILE_ID = r"[a-z]{0,2}[1-9][0-9]*"
CASE_ID = rf"{FILE_ID}(?:\.[0-9]+)+"
TS_TEST_SUFFIX = r"\.(?:test|spec)\.[cm]?[jt]sx?"
PY_TEST = re.compile(r"(?:test_.+|.+_test)\.py$")
TS_TEST = re.compile(rf".+{TS_TEST_SUFFIX}$")
_PY_FILE_ID = re.compile(rf"({FILE_ID})_[a-z0-9_]+_test\.py")
_TS_FILE_ID = re.compile(rf"({FILE_ID})-.+{TS_TEST_SUFFIX}")
TITLE_LINK = re.compile(r"^# [^\n]*\[[^\n]+\]\(([^)\n]+)\)", re.MULTILINE)


def list_story_sources(repo: Repo, ctx: Context) -> list[str]:
    oracle = ctx.config.source_oracle
    return [
        path
        for path in ctx.paths(repo)
        if "node_modules" not in PurePosixPath(path).parts
        and (
            (path.endswith(".md") and oracle.classify_directory(PurePosixPath(path).parent.as_posix()).is_test)
            or (is_test_name(PurePosixPath(path).name) and oracle.is_test_file(path))
        )
    ]


def is_test_name(name: str) -> bool:
    return bool(PY_TEST.fullmatch(name) or TS_TEST.fullmatch(name))


def find_file_id(name: str) -> str | None:
    match = _PY_FILE_ID.fullmatch(name) or _TS_FILE_ID.fullmatch(name)
    return match.group(1) if match else None


def has_story_marker(content: str) -> bool:
    return content.partition("\n")[0] in {"# @story", "// @story"}


def find_title_target(content: str) -> str:
    match = TITLE_LINK.search(content)
    return PurePosixPath(match.group(1)).name if match else ""
