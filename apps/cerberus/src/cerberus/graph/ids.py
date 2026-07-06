from __future__ import annotations

import posixpath
import re

_NON_WORD = re.compile(r"\W+")


def file_id(rel_path: str) -> str:
    stem = posixpath.splitext(rel_path)[0]
    return _NON_WORD.sub("_", stem.lower()).strip("_")


def symbol_id(owner_file_id: str, name: str) -> str:
    slug = _NON_WORD.sub("_", name.lower()).strip("_")
    return f"{owner_file_id}__{slug}"
