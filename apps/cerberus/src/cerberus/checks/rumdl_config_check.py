from __future__ import annotations

import tomllib
from typing import Any

from cerberus.context import Context
from cerberus.model import CheckResult, Repo, Scope

ID = "rumdl-config"
SUMMARY = "`.rumdl.toml` carries the org-canonical rule config (per-repo `exclude` allowed)"
SCOPE = Scope.CONTENT

PATH = ".rumdl.toml"

CANONICAL = """\
[global]
disable = [
    "MD013", # line-length
    "MD022", # blanks-around-headings
    "MD031", # blanks-around-fences
    "MD032", # blanks-around-lists
    "MD033", # no-inline-html
]

# no-duplicate-heading
[MD024]
siblings-only = true
"""


def _rules_only(parsed: dict[str, Any]) -> dict[str, Any]:
    """The rule config with `global.exclude` dropped — exclude is a per-repo path list."""
    out = {key: dict(value) if isinstance(value, dict) else value for key, value in parsed.items()}
    global_table = out.get("global")
    if isinstance(global_table, dict):
        global_table.pop("exclude", None)
    return out


def _exclude(parsed: dict[str, Any]) -> list[str]:
    global_table = parsed.get("global")
    if isinstance(global_table, dict) and isinstance(global_table.get("exclude"), list):
        return [str(entry) for entry in global_table["exclude"]]
    return []


def _render(exclude: list[str]) -> str:
    if not exclude:
        return CANONICAL
    entries = ", ".join(f'"{path}"' for path in exclude)
    return CANONICAL.replace("]\n", f"]\nexclude = [{entries}]\n", 1)


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    content = ctx.file(repo, PATH)

    if content is None:
        if ctx.fix:
            ctx.write_file(repo, PATH, CANONICAL)
        else:
            res.fail(f"no {PATH} at repo root")
        return res

    try:
        parsed = tomllib.loads(content)
    except tomllib.TOMLDecodeError as err:
        res.error(f"could not parse {PATH}: {err}")
        return res

    if _rules_only(parsed) != _rules_only(tomllib.loads(CANONICAL)):
        if ctx.fix:
            ctx.write_file(repo, PATH, _render(_exclude(parsed)))
        else:
            res.fail(f"{PATH} rule config does not match the org canonical")
        return res

    res.ok(f"{PATH} matches the org canonical")
    return res
