from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any

from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "rumdl"
SUMMARY = "`.rumdl.toml` carries the org-canonical rule config (per-repo `exclude` allowed)"
SCOPE = Scope.CONTENT

PATH = ".rumdl.toml"


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


def _render(canonical: str, exclude: list[str]) -> str:
    if not exclude:
        return canonical
    entries = ", ".join(f'"{path}"' for path in exclude)
    return canonical.replace("]\n", f"]\nexclude = [{entries}]\n", 1)


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    canonical = ctx.config.rumdl_canonical
    content = ctx.file(repo, PATH)

    if content is None:
        if ctx.fix:
            ctx.write_file(repo, PATH, canonical)
        else:
            res.fail(f"no {PATH} at repo root")
        return res

    try:
        parsed = tomllib.loads(content)
    except tomllib.TOMLDecodeError as err:
        res.error(f"could not parse {PATH}: {err}")
        return res

    if _rules_only(parsed) != _rules_only(tomllib.loads(canonical)):
        if ctx.fix:
            ctx.write_file(repo, PATH, _render(canonical, _exclude(parsed)))
        else:
            res.fail(f"{PATH} rule config does not match the org canonical")
        return res

    res.ok(f"{PATH} matches the org canonical")
    return res
