"""Shared machinery for the `story-tests-py`/`story-tests-ts` checks.

A "package" is a uv/bun workspace member, or the repo root when the language
has no workspace (a single-project repo). A package needs user-story tests
when it exposes a public interface — a CLI entry point, a published
`exports`/`main` surface, or tests of its own already exist for it — and
having none is a FAIL; not needing them is silently skipped. Docs already
present are always validated for consistency, whether or not the package
was judged to need them.

Story docs live at `<package>/tests/stories/*.md`, or — when tests are torn
out to a top-level `tests/<package-basename>/` directory, as some repos do —
at `tests/<package-basename>/stories/*.md`. Numbered docs (`# N. Title` /
`## N.M Title` / `### N.M.K Title`) pair with same-numbered test files in the
same directory: `test_N_slug.py` for Python (underscores — a hyphen isn't a
valid identifier character), `N-slug.test.ts` for TypeScript (kebab-case, per
`unicorn/filename-case`). Each language's doc filename follows its own test
filename's separator.
"""

from __future__ import annotations

import ast
import json
import re
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo

PY_TEST_NAME = re.compile(r"^test_(\d+)_[^/]+\.py$")
TS_TEST_NAME = re.compile(r"^(\d+)-[^/]+\.(?:test|spec)\.tsx?$")

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_APOSTROPHE = re.compile(r"'")
_NON_WORD = re.compile(r"[^\w\s]")

_STORIES_PATH_PARTS = 2  # a stories-dir path is at least "<dir>/stories/<file>"
_DOC_NAME = re.compile(r"^\d+[_-][^/]+\.md$")  # `_` (Python docs) or `-` (TypeScript docs, kebab-case)
_LEADING_NUMBER = re.compile(r"^\d+")
_DOC_TITLE = re.compile(r"^# (\d+)\. (.+)$")
_STORY_HEADER = re.compile(r"^## (\d+\.\d+) (.+)$")
_CRITERION_HEADER = re.compile(r"^### (\d+(?:\.\d+)+) (.+)$")
_LINKED_TITLE = re.compile(r"^\[(?P<title>.+)\]\((?P<target>[^)]+)\)$")
_BALANCED_PARENS = r"\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)"
_TS_TEST_CALL = re.compile(
    rf"\b(?:test|it)(?:\.\w+)*(?:{_BALANCED_PARENS}\s*)?\(\s*"
    rf"(?P<quote>['\"`])(?P<id>\d+(?:\.\d+)+)\s+(?P<title>(?:(?!(?P=quote)).)*?)(?P=quote)",
    re.DOTALL,
)
_PY_ANY_TEST = re.compile(r"^test_.+\.py$")
_TS_ANY_TEST = re.compile(r".+\.(?:test|spec)\.tsx?$")
_TEST_HARNESS_PACKAGE = "tests"  # a workspace member reserved for cross-package test tooling, never a product itself


@dataclass(frozen=True)
class StoryTest:
    story_id: str
    title: str
    file: str


@dataclass(frozen=True)
class Header:
    story_id: str
    title: str


@dataclass(frozen=True)
class Language:
    name: str
    manifest_name: str
    own_test_name: re.Pattern[str]
    collect_tests: Callable[[list[str], Callable[[str], str | None]], dict[str, StoryTest]]
    package_dirs: Callable[[Repo, Context, list[str]], list[str]]
    needs_story_tests: Callable[[str, Repo, Context, list[str]], bool]


@dataclass(frozen=True)
class _Group:
    directory: str
    docs: dict[str, str]
    tests: dict[str, StoryTest]


def word_sequence(title: str) -> list[str]:
    """A title's comparable words: case folds, apostrophes drop, and camelCase/punctuation are word breaks.

    A test function name can't carry an apostrophe, a dot, or a capital letter,
    so a header describing the same criterion in prose ("the repo's package.json",
    "includeEntryExports") must still compare equal to the derived test title
    ("the repos package json", "include entry exports").
    """
    folded = _APOSTROPHE.sub("", title)
    spaced = _CAMEL_BOUNDARY.sub(" ", folded)
    return _NON_WORD.sub(" ", spaced).lower().split()


def _strip_link(rest: str) -> str:
    linked = _LINKED_TITLE.match(rest)
    return linked.group("title") if linked else rest


def parse_headers(doc: str) -> dict[str, Header]:
    headers: dict[str, Header] = {}
    for line in doc.splitlines():
        header = _CRITERION_HEADER.match(line)
        if header:
            story_id, rest = header.group(1), header.group(2)
            headers[story_id] = Header(story_id, _strip_link(rest))
    return headers


def _section_files(tests: dict[str, StoryTest]) -> dict[str, str]:
    return {test.story_id.split(".")[0]: test.file for test in tests.values()}


def render_linked_doc(doc: str, tests: dict[str, StoryTest]) -> str:
    """Each doc's h1 title linked to its section's test file; h2/h3 headers always plain."""
    files = _section_files(tests)
    rendered: list[str] = []
    for raw in doc.splitlines(keepends=True):
        stripped = raw.rstrip("\n")
        newline = raw[len(stripped) :]
        doc_title = _DOC_TITLE.match(stripped)
        story = _STORY_HEADER.match(stripped)
        criterion = _CRITERION_HEADER.match(stripped)
        if doc_title:
            section, title = doc_title.group(1), _strip_link(doc_title.group(2))
            file = files.get(section)
            rendered.append(raw if file is None else f"# {section}. [{title}]({file}){newline}")
        elif story:
            story_id, title = story.group(1), _strip_link(story.group(2))
            rendered.append(f"## {story_id} {title}{newline}")
        elif criterion:
            story_id, title = criterion.group(1), _strip_link(criterion.group(2))
            rendered.append(f"### {story_id} {title}{newline}")
        else:
            rendered.append(raw)
    return "".join(rendered)


def split_id_and_title(func_name: str) -> tuple[str, str]:
    tokens = func_name.removeprefix("test_").split("_")
    cut = 0
    while cut < len(tokens) and tokens[cut].isdigit():
        cut += 1
    return ".".join(tokens[:cut]), " ".join(tokens[cut:])


def collect_py_tests(test_paths: list[str], read: Callable[[str], str | None]) -> dict[str, StoryTest]:
    tests: dict[str, StoryTest] = {}
    for path in sorted(test_paths):
        content = read(path)
        if content is None:
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                story_id, title = split_id_and_title(node.name)
                if story_id:
                    tests[story_id] = StoryTest(story_id, title, path.rsplit("/", 1)[-1])
    return tests


def collect_ts_tests(test_paths: list[str], read: Callable[[str], str | None]) -> dict[str, StoryTest]:
    tests: dict[str, StoryTest] = {}
    for path in sorted(test_paths):
        content = read(path)
        if content is None:
            continue
        for match in _TS_TEST_CALL.finditer(content):
            story_id = match.group("id")
            title = match.group("title").strip()
            tests[story_id] = StoryTest(story_id, title, path.rsplit("/", 1)[-1])
    return tests


def _package_prefixes(package: str) -> list[str]:
    """Where a package's own files may live: co-located, or torn out to a top-level tests/<basename>/."""
    if not package:
        return [""]
    basename = package.rsplit("/", 1)[-1]
    return [f"{package}/", f"tests/{basename}/"]


def under_package(path: str, package: str) -> bool:
    return any(path.startswith(prefix) for prefix in _package_prefixes(package))


def _dir_matches_glob(directory: str, glob: str) -> bool:
    dir_parts = directory.split("/")
    glob_parts = glob.rstrip("/").split("/")
    return len(dir_parts) == len(glob_parts) and all(g in {"*", d} for g, d in zip(glob_parts, dir_parts, strict=True))


def _member_dirs(paths: list[str], globs: list[str], manifest_name: str) -> list[str]:
    suffix = f"/{manifest_name}"
    dirs = {path[: -len(suffix)] for path in paths if path.endswith(suffix)}
    return sorted(d for d in dirs if any(_dir_matches_glob(d, glob) for glob in globs))


def _without_test_harness(dirs: list[str]) -> list[str]:
    return [d for d in dirs if d.split("/", 1)[0] != _TEST_HARNESS_PACKAGE]


def _py_package_dirs(repo: Repo, ctx: Context, paths: list[str]) -> list[str]:
    content = ctx.file(repo, "pyproject.toml")
    if content is None:
        return []
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return []
    tool = data.get("tool")
    uv = tool.get("uv") if isinstance(tool, dict) else None
    workspace = uv.get("workspace") if isinstance(uv, dict) else None
    if isinstance(workspace, dict):
        members = [g for g in workspace.get("members", []) if isinstance(g, str)]
        return _without_test_harness(_member_dirs(paths, members, "pyproject.toml"))
    return [""] if isinstance(data.get("project"), dict) else []


def ts_member_dirs(repo: Repo, ctx: Context, paths: list[str]) -> list[str]:
    """Every bun workspace member dir — including the tests/ harness members that package_dirs excludes."""
    content = ctx.file(repo, "package.json")
    if content is None:
        return []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    workspaces = data.get("workspaces")
    globs: list[str] | None = None
    if isinstance(workspaces, list):
        globs = [g for g in workspaces if isinstance(g, str)]
    elif isinstance(workspaces, dict):
        globs = [g for g in workspaces.get("packages", []) if isinstance(g, str)]
    if globs is not None:
        return _member_dirs(paths, globs, "package.json")
    return [""]


def _ts_package_dirs(repo: Repo, ctx: Context, paths: list[str]) -> list[str]:
    return _without_test_harness(ts_member_dirs(repo, ctx, paths))


def _py_needs_story_tests(package: str, repo: Repo, ctx: Context, paths: list[str]) -> bool:
    manifest_path = f"{package}/pyproject.toml" if package else "pyproject.toml"
    content = ctx.file(repo, manifest_path)
    if content is not None:
        try:
            project = tomllib.loads(content).get("project")
        except tomllib.TOMLDecodeError:
            project = None
        if isinstance(project, dict) and project.get("scripts"):
            return True
    return any(under_package(path, package) and _PY_ANY_TEST.match(path.rsplit("/", 1)[-1]) for path in paths)


def _ts_needs_story_tests(package: str, repo: Repo, ctx: Context, paths: list[str]) -> bool:
    manifest_path = f"{package}/package.json" if package else "package.json"
    content = ctx.file(repo, manifest_path)
    if content is not None:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and (data.get("bin") or data.get("exports") or data.get("main")):
            return True
    return any(under_package(path, package) and _TS_ANY_TEST.match(path.rsplit("/", 1)[-1]) for path in paths)


PY = Language("Python", "pyproject.toml", PY_TEST_NAME, collect_py_tests, _py_package_dirs, _py_needs_story_tests)
TS = Language("TypeScript", "package.json", TS_TEST_NAME, collect_ts_tests, _ts_package_dirs, _ts_needs_story_tests)


def _grouped_by_stories_dir(paths: list[str], name: re.Pattern[str]) -> dict[str, list[str]]:
    dirs: dict[str, list[str]] = {}
    for path in paths:
        parts = path.split("/")
        if len(parts) < _STORIES_PATH_PARTS or parts[-2] != "stories" or "node_modules" in parts:
            continue
        if name.match(parts[-1]):
            dirs.setdefault("/".join(parts[:-1]), []).append(path)
    return dirs


def _headers_of(group: _Group) -> dict[str, Header]:
    headers: dict[str, Header] = {}
    for content in group.docs.values():
        headers.update(parse_headers(content))
    return headers


def _check_presence(res: CheckResult, group: _Group, headers: dict[str, Header]) -> None:
    orphan_tests = sorted(set(group.tests) - set(headers))
    if orphan_tests:
        res.fail(f"{group.directory}: story test(s) with no matching ### header: {', '.join(orphan_tests)}")

    orphan_headers = sorted(set(headers) - set(group.tests))
    if orphan_headers:
        res.fail(f"{group.directory}: story-doc ### header(s) with no matching test: {', '.join(orphan_headers)}")


def _check_title_drift(res: CheckResult, group: _Group, headers: dict[str, Header]) -> None:
    for story_id in sorted(set(group.tests) & set(headers)):
        header_title, test_title = headers[story_id].title, group.tests[story_id].title
        if word_sequence(header_title) != word_sequence(test_title):
            res.fail(f"{group.directory}: header/test title drift for {story_id} — header={header_title!r} test={test_title!r}")


def _check_own_section(res: CheckResult, group: _Group) -> None:
    for doc_path, content in sorted(group.docs.items()):
        name = doc_path.rsplit("/", 1)[-1]
        leading = _LEADING_NUMBER.match(name)
        section = leading.group() if leading else name
        strays = sorted(story_id for story_id in parse_headers(content) if story_id.split(".")[0] != section)
        if strays:
            res.fail(f"{doc_path}: story header(s) filed in the wrong section doc: {', '.join(strays)}")


def _check_header_links(res: CheckResult, ctx: Context, repo: Repo, group: _Group) -> None:
    for doc_path, content in sorted(group.docs.items()):
        relinked = render_linked_doc(content, group.tests)
        if relinked == content:
            continue
        if ctx.fix:
            ctx.write_file(repo, doc_path, relinked)
        else:
            res.fail(f"{doc_path}: story header links are stale; run with --fix")


def _check_group(res: CheckResult, ctx: Context, repo: Repo, group: _Group) -> None:
    headers = _headers_of(group)
    _check_presence(res, group, headers)
    _check_title_drift(res, group, headers)
    _check_own_section(res, group)
    _check_header_links(res, ctx, repo, group)


def run_story_check(repo: Repo, ctx: Context, res: CheckResult, language: Language) -> None:
    paths = ctx.paths(repo)
    packages = language.package_dirs(repo, ctx, paths)
    if not packages:
        res.skip(f"no {language.name} packages")
        return

    doc_dirs = _grouped_by_stories_dir(paths, _DOC_NAME)
    own_dirs = _grouped_by_stories_dir(paths, language.own_test_name)
    all_story_dirs = set(doc_dirs) | set(own_dirs)

    def read(path: str) -> str | None:
        return ctx.file(repo, path)

    did_something = False
    for package in sorted(packages):
        owned = sorted(d for d in all_story_dirs if under_package(d, package))
        if not owned:
            if language.needs_story_tests(package, repo, ctx, paths):
                res.fail(f"{package or '.'}: exposes a public interface but has no tests/**/stories/*.md user-story tests")
                did_something = True
            continue

        did_something = True
        for directory in owned:
            docs = {path: content for path in doc_dirs.get(directory, []) if (content := read(path)) is not None}
            tests = language.collect_tests(own_dirs.get(directory, []), read)
            _check_group(res, ctx, repo, _Group(directory, docs, tests))

    if not did_something:
        res.skip(f"no {language.name} package needs story-based tests")
    elif not res.problems:
        res.ok("every story criterion has a matching, title-matched test")
