from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from cerberus.bites.story_files import is_test_name, list_story_sources
from cerberus.model import CheckResult, Repo, Scope

if TYPE_CHECKING:
    from cerberus.context import Context

ID = "unique_test_names"
SUMMARY = "executable test basenames are unique across the repository"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    names: defaultdict[str, list[str]] = defaultdict(list)
    for path in list_story_sources(repo, ctx):
        name = path.rsplit("/", 1)[-1]
        if is_test_name(name):
            names[name].append(path)
    for name, paths in sorted(names.items()):
        if len(paths) > 1:
            res.fail(f"duplicate test basename {name}: {', '.join(sorted(paths))}")
    if not res.problems:
        res.ok(SUMMARY)
    return res
