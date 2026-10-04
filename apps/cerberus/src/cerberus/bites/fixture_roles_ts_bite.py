"""Fixture entry points for flat and domain TypeScript story suites.

Flat suites use #fixtures with fixtures/index.ts and fixtures/act.ts.
Each nested story directory owns a domain module named after that directory.
ESLint's test-seam-only-imports rule checks story imports and bindings.
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
SUMMARY = "story suites use #fixtures or a local domain module"
SCOPE = Scope.CONTENT

_FIXTURES_ALIAS = "#fixtures"
_INDEX_TARGET = "./fixtures/index.ts"
_SUITE_STORY_TEST = re.compile(r"^(tests/[^/]+)/stories/(?:[^/]+/)*[^/]+\.test\.tsx?$")
_OK_MESSAGE = "every story directory has a fixture entry point"


def _story_directories(paths: list[str]) -> dict[str, set[str]]:
    directories: dict[str, set[str]] = {}
    for path in paths:
        if match := _SUITE_STORY_TEST.match(path):
            directories.setdefault(match.group(1), set()).add(path.rsplit("/", 1)[0])
    return directories


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
    directories = _story_directories(paths)
    suites = sorted(directories.keys() & set(members))
    if not suites:
        res.skip("no torn-out story suites")
        return res

    path_set = frozenset(paths)
    for suite in suites:
        for directory in sorted(directories[suite]):
            if directory == f"{suite}/stories":
                _check_alias(res, suite, test_seam.parse_manifest(ctx.file(repo, f"{suite}/package.json")))
                act_path = f"{suite}/fixtures/act.ts"
                if act_path not in path_set:
                    res.fail(f"{act_path}: missing — act.ts is the fixture module that drives the subject package")
            else:
                domain = directory.rsplit("/", 1)[1]
                entry = f"{directory}/{domain}.ts"
                if entry not in path_set:
                    res.fail(f"{entry}: missing — each story domain owns its test module")

    if not res.problems:
        res.ok(_OK_MESSAGE)
    return res
