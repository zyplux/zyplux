from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

from pydantic import ValidationError

from cerberus.config import parse_overlay
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "cerberus_schema"
SUMMARY = "repository configuration matches the Cerberus schema"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    path = str(ctx.config_path) if ctx.config_path is not None else "cerberus.toml"
    try:
        text = ctx.config_path.read_text() if ctx.config_path is not None else ctx.file(repo, path)
        if text is not None:
            parse_overlay(text)
    except ValidationError as exc:
        for problem in exc.errors(include_url=False, include_input=False, include_context=False):
            location = ".".join(str(part) for part in problem["loc"])
            res.fail(f"{path}: {location}: {problem['msg']}")
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        res.fail(f"{path}: {exc}")
    else:
        res.ok("configuration matches the schema" if text is not None else "using bundled defaults")
    return res
