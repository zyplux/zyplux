"""The fixture-role layout for TypeScript test suites: a torn-out suite's
fixtures live in role modules under `fixtures/` — arrange builds the world,
act drives the subject, assert verifies — composed by `fixtures/index.ts`,
the sole target of the `#fixtures` alias the suite's story tests import from.
Two facts keep the roles honest: the alias maps to `./fixtures/index.ts`
(with `fixtures/act.ts` present beside it), and the suite's subject package —
the workspace member the suite is torn out of, `tests/<basename>` paired with
`<dir>/<basename>` — is imported only by `act.ts`; its `./contracts` seam
alone is importable from any role module. Companion to `cli_ts_test_seam`/
`lib_ts_test_seam`, which seal the story files themselves onto `#` aliases.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from cerberus.bites import story_docs, test_seam
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "fixture_roles_ts"
SUMMARY = "test suites compose fixtures from role modules; only act.ts drives the subject package"
SCOPE = Scope.CONTENT

_FIXTURES_ALIAS = "#fixtures"
_INDEX_TARGET = "./fixtures/index.ts"
_CONTRACTS_SUBPATH = "/contracts"
_SUITE_STORY_TEST = re.compile(r"^(tests/[^/]+)/stories/[^/]+\.test\.tsx?$")
_OK_MESSAGE = "every suite's #fixtures alias targets fixtures/index.ts and only act.ts drives the subject package"


def _story_suites(paths: list[str]) -> set[str]:
    return {match.group(1) for path in paths if (match := _SUITE_STORY_TEST.match(path))}


def _subject_names(repo: Repo, ctx: Context, members: list[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    for member in members:
        if not member or member.startswith("tests/"):
            continue
        name = test_seam.parse_manifest(ctx.file(repo, f"{member}/package.json")).get("name")
        if isinstance(name, str):
            names[member.rsplit("/", 1)[-1]] = name
    return names


def _check_alias(res: CheckResult, suite: str, manifest: dict[str, object]) -> None:
    imports = manifest.get("imports")
    target = imports.get(_FIXTURES_ALIAS) if isinstance(imports, dict) else None
    if target is None:
        res.fail(f"{suite}/package.json: no '{_FIXTURES_ALIAS}' alias targeting '{_INDEX_TARGET}'")
    elif target != _INDEX_TARGET:
        res.fail(f"{suite}/package.json: '{_FIXTURES_ALIAS}' must map to '{_INDEX_TARGET}', got '{target}'")


def _check_subject_imports(res: CheckResult, suite: str, subject: str, modules: dict[str, str], act_path: str) -> None:
    contracts_seam = f"{subject}{_CONTRACTS_SUBPATH}"
    for path, content in sorted(modules.items()):
        if path == act_path:
            continue
        for specifier in test_seam.import_specifiers(content):
            if specifier != subject and not specifier.startswith(f"{subject}/"):
                continue
            if specifier == contracts_seam:
                continue
            res.fail(f"{path}: only fixtures/act.ts may import the subject package — '{specifier}'")


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    paths = ctx.paths(repo)
    members = story_docs.ts_member_dirs(repo, ctx, paths)
    if not members:
        res.skip("no TypeScript packages")
        return res
    suites = sorted(_story_suites(paths) & set(members))
    if not suites:
        res.skip("no torn-out story suites")
        return res

    subjects = _subject_names(repo, ctx, members)
    path_set = frozenset(paths)
    for suite in suites:
        _check_alias(res, suite, test_seam.parse_manifest(ctx.file(repo, f"{suite}/package.json")))
        act_path = f"{suite}/fixtures/act.ts"
        if act_path not in path_set:
            res.fail(f"{act_path}: missing — act.ts is the fixture module that drives the subject package")
        subject = subjects.get(suite.rsplit("/", 1)[-1])
        if subject is None:
            continue
        modules = {
            path: content
            for path in paths
            if path.startswith(f"{suite}/fixtures/") and (content := ctx.file(repo, path)) is not None
        }
        _check_subject_imports(res, suite, subject, modules, act_path)

    if not res.problems:
        res.ok(_OK_MESSAGE)
    return res
