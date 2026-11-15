"""Require repo-wide unique test identifiers across Python and JavaScript suites."""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from cerberus.model import CheckResult, Repo, Scope
from cerberus.story_tests.discover_test_cases import list_python_tests, list_typescript_cases, split_python_test_name
from cerberus.story_tests.story_source_discovery import PY_TEST, find_file_id, is_test_name, list_story_sources

if TYPE_CHECKING:
    from collections.abc import Iterator

    from cerberus.context import Context

ID = "unique_test_ids"
SUMMARY = "test IDs are unique across the repository"
SCOPE = Scope.CONTENT


def _case_ids(path: str, name: str, content: str) -> Iterator[tuple[int, str]]:
    if PY_TEST.fullmatch(name):
        return ((test.lineno, split_python_test_name(test.name)[0]) for test in list_python_tests(content))
    return list_typescript_cases(path, content)


def _check_cases(res: CheckResult, path: str, file_id: str, cases: Iterator[tuple[int, str]]) -> None:
    seen = set()
    for line, case_id in cases:
        if case_id.partition(".")[0] != file_id:
            res.fail(f"{path}:{line}: test case must start with {file_id}. followed by a number")
        elif case_id in seen:
            res.fail(f"{path}:{line}: duplicate test case ID {case_id}")
        seen.add(case_id)
    if not seen:
        res.fail(f"{path}: no test cases found for ID {file_id}")


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    files: defaultdict[str, list[str]] = defaultdict(list)
    for path in list_story_sources(repo, ctx):
        name = PurePosixPath(path).name
        if not is_test_name(name):
            continue
        file_id = find_file_id(name)
        if file_id is None:
            res.fail(
                f"{path}: use <id>_subject_test.py or <id>-subject.test.ts with a number and optional suite letters"
            )
            continue
        files[file_id].append(path)
        try:
            _check_cases(res, path, file_id, _case_ids(path, name, ctx.file(repo, path) or ""))
        except SyntaxError:
            res.fail(f"{path}: could not parse test cases")
    for file_id, paths in sorted(files.items()):
        if len(paths) > 1:
            res.fail(f"duplicate test file ID {file_id}: {', '.join(sorted(paths))}")
    if not res.problems:
        res.ok(SUMMARY)
    return res
