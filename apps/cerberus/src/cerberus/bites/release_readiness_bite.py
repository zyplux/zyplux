from __future__ import annotations

from typing import TYPE_CHECKING

from airlock.content_hash import validate_contents
from airlock.errors import RELEASE_ERRORS
from airlock.notes import load_prepared_targets

from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "release_readiness"
SUMMARY = "release notes, tracking versions and content fingerprints are ready for publication"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    if ctx.file(repo, "airlock-targets.toml") is None:
        res.skip("no airlock-targets.toml — repo publishes nothing")
        return res
    try:
        for target, _ in load_prepared_targets(root=ctx.source.root):
            validate_contents(target)
    except ValueError as exc:
        res.fail(str(exc))
    except RELEASE_ERRORS as exc:
        res.error(str(exc))
    else:
        res.ok(SUMMARY)
    return res
