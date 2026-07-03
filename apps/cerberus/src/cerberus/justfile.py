from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cerberus import proc


class JustfileError(RuntimeError):
    pass


_MOD_STATEMENT = re.compile(r"^mod\??\s+(?P<name>\w+)(?:\s+(?P<quoted_path>'[^']*'|\"[^\"]*\"))?\s*(?:#.*)?$")


@dataclass(frozen=True)
class Justfile:
    recipes: dict[str, list[str]]
    aliases: dict[str, str]
    bodies: dict[str, str]


def _join_body(body: list[list[Any]] | None) -> str:
    """Flatten a `just --dump` body to text.

    A body is a list of lines; each line is a list of fragments that are either
    literal strings or interpolation nodes (nested lists). Only literal markers
    are matched downstream, so interpolations collapse to a single space.
    """
    if not body:
        return ""
    return "\n".join("".join(fragment if isinstance(fragment, str) else " " for fragment in line) for line in body)


def _materialize_module_stubs(content: str, root: Path) -> None:
    """Satisfy `mod` statements with empty source files so `just --dump` can run.

    Module recipes are namespaced (`name::recipe`) and outside the root-level
    rules cerberus enforces, so an empty stub at the declared (or implicit
    `name/justfile`) path preserves every fact the checks read.
    """
    for line in content.splitlines():
        statement = _MOD_STATEMENT.match(line)
        if statement is None:
            continue
        quoted_path = statement.group("quoted_path")
        stub = Path(quoted_path[1:-1]) if quoted_path else Path(statement.group("name")) / "justfile"
        resolved = (root / stub).resolve()
        if not resolved.is_relative_to(root):
            continue
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.touch()


def parse(content: str) -> Justfile:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "justfile"
        path.write_text(content)
        _materialize_module_stubs(content, Path(tmp).resolve())
        try:
            completed = proc.run(["just", "-f", str(path), "--dump", "--dump-format", "json"])
        except proc.ToolNotFoundError as err:
            raise JustfileError(str(err)) from err
    if completed.returncode != 0:
        raise JustfileError(completed.stderr.strip() or "just --dump failed")
    data = json.loads(completed.stdout)
    aliases = {name: spec["target"] for name, spec in data.get("aliases", {}).items()}
    recipes: dict[str, list[str]] = {}
    bodies: dict[str, str] = {}
    for name, spec in data.get("recipes", {}).items():
        recipes[name] = [dep["recipe"] for dep in spec.get("dependencies", [])]
        bodies[name] = _join_body(spec.get("body"))
    return Justfile(recipes=recipes, aliases=aliases, bodies=bodies)


def is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    it = iter(haystack)
    return all(item in it for item in needle)
