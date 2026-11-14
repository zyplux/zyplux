from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

PY_TEST = re.compile(r"(?:test_.+|.+_test)\.py$")
TS_TEST = re.compile(r".+\.(?:test|spec)\.[cm]?[jt]sx?$")
PY_STORY = re.compile(r"test_\d+_.+\.py$")
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


def find_title_target(content: str) -> str:
    match = TITLE_LINK.search(content)
    return PurePosixPath(match.group(1)).name if match else ""
