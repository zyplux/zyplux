"""The fixture-role layout for TypeScript test suites: a torn-out suite's
fixtures live in role modules under `fixtures/` — arrange builds the world,
act drives the subject, assert verifies — composed by `fixtures/index.ts`,
the sole target of the `#fixtures` alias the suite's story tests import from.
This bite pins the alias mapping (`./fixtures/index.ts`, with `fixtures/act.ts`
present beside it) — a manifest-shape fact no editor-time tool can see. Which
role modules may import the suite's subject package is enforced in-editor
instead, by the `@zyplux/fixture-role-imports` ESLint rule (arrange.ts and
act.ts may; every other fixture module may not, its `./contracts` seam
excepted). Companion to `cli_ts_test_seam`/`lib_ts_test_seam`, which seal the
story files themselves onto `#` aliases.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from cerberus.bites import test_seam
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "fixture_roles_ts"
SUMMARY = "test suites compose fixtures from role modules; the #fixtures alias targets fixtures/index.ts"
SCOPE = Scope.CONTENT

_FIXTURES_ALIAS = "#fixtures"
_INDEX_TARGET = "./fixtures/index.ts"
_SUITE_STORY_TEST = re.compile(r"^(tests/[^/]+)/stories/[^/]+\.test\.tsx?$")
_OK_MESSAGE = "every suite's #fixtures alias targets fixtures/index.ts with fixtures/act.ts present"


def _story_suites(paths: list[str]) -> set[str]:
    return {match.group(1) for path in paths if (match := _SUITE_STORY_TEST.match(path))}


def _check_alias(res: CheckResult, suite: str, manifest: dict[str, object]) -> None:
    imports = manifest.get("imports")
    target = imports.get(_FIXTURES_ALIAS) if isinstance(imports, dict) else None
    if target is None:
        res.fail(f"{suite}/package.json: no '{_FIXTURES_ALIAS}' alias targeting '{_INDEX_TARGET}'")
    elif target != _INDEX_TARGET:
        res.fail(f"{suite}/package.json: '{_FIXTURES_ALIAS}' must map to '{_INDEX_TARGET}', got '{target}'")


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    paths_and_members = test_seam.ts_paths_and_members(repo, ctx, res)
    if paths_and_members is None:
        return res
    paths, members = paths_and_members
    suites = sorted(_story_suites(paths) & set(members))
    if not suites:
        res.skip("no torn-out story suites")
        return res

    path_set = frozenset(paths)
    for suite in suites:
        _check_alias(res, suite, test_seam.parse_manifest(ctx.file(repo, f"{suite}/package.json")))
        act_path = f"{suite}/fixtures/act.ts"
        if act_path not in path_set:
            res.fail(f"{act_path}: missing — act.ts is the fixture module that drives the subject package")

    if not res.problems:
        res.ok(_OK_MESSAGE)
    return res
