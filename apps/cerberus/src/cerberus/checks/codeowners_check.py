from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "codeowners"
SUMMARY = "CODEOWNERS present and covers /.github/"
SCOPE = Scope.CONTENT

_LOCATIONS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")


def _covers_github(pattern: str) -> bool:
    if pattern == "*":
        return True
    top = pattern.lstrip("/").split("/", 1)[0]
    return top == ".github"


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)

    content = next((c for path in _LOCATIONS if (c := ctx.file(repo, path)) is not None), None)
    if content is None:
        res.fail("no CODEOWNERS file")
        return res

    owned_lines = [line for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#") and "@" in line]
    if not owned_lines:
        res.fail("CODEOWNERS has no ownership rules")
    elif not any(_covers_github(line.split()[0]) for line in owned_lines):
        res.fail("CODEOWNERS does not cover `/.github/`")

    if not res.problems:
        res.ok("CODEOWNERS present, covers /.github/")
    return res
