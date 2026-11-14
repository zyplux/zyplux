"""Python user stories pair package-owned documentation with pytest criteria."""

from __future__ import annotations

import ast
import re
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cerberus import workspaces
from cerberus.bites.story_files import PY_STORY, PY_TEST, TS_TEST, find_title_target, list_story_sources

if TYPE_CHECKING:
    from collections.abc import Iterator

    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_APOSTROPHE = re.compile(r"'")
_NON_WORD = re.compile(r"[^\w\s]")

_DOC_NAME = re.compile(r"^\d+[_-][^/]+\.md$")  # `_` (Python docs) or `-` (TypeScript docs, kebab-case)
_PY_DOC_NAME = re.compile(r"^\d+_[^/]+\.md$")
_LEADING_NUMBER = re.compile(r"^\d+")
_DOC_TITLE = re.compile(r"^# (\d+)\. (.+)$")
_STORY_HEADER = re.compile(r"^## (\d+\.\d+) (.+)$")
_CRITERION_HEADER = re.compile(r"^### (\d+(?:\.\d+)+) (.+)$")
_LINKED_TITLE = re.compile(r"^\[(?P<title>.+)\]\((?P<target>[^)]+)\)$")


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
    return {header.story_id: header for header in _iter_headers(doc)}


def _iter_headers(doc: str) -> Iterator[Header]:
    for line in doc.splitlines():
        header = _CRITERION_HEADER.match(line)
        if header:
            story_id, rest = header.group(1), header.group(2)
            yield Header(story_id, _strip_link(rest))


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


def _collect_tests(repo: Repo, ctx: Context, res: CheckResult, paths: list[str]) -> dict[str, StoryTest]:
    tests: dict[str, StoryTest] = {}
    for path in sorted(paths):
        try:
            tree = ast.parse(ctx.file(repo, path) or "")
        except SyntaxError:
            res.fail(f"{path}: could not parse story tests")
            continue
        count = 0
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            story_id, title = split_id_and_title(node.name)
            if story_id:
                count += 1
                if story_id in tests:
                    res.fail(f"{path}: duplicate story test ID {story_id}")
                tests[story_id] = StoryTest(story_id, title, path.rsplit("/", 1)[-1])
        if not count:
            res.fail(f"{path}: no numbered story test IDs")
    return tests


def _package_prefixes(package: str) -> list[str]:
    """Where a package's own files may live: co-located, or torn out to a top-level tests/<basename>/."""
    if not package:
        return [""]
    basename = package.rsplit("/", 1)[-1]
    return [f"{package}/", f"tests/{basename}/"]


def under_package(path: str, package: str) -> bool:
    return any(path.startswith(prefix) for prefix in _package_prefixes(package))


def list_python_packages(repo: Repo, ctx: Context, paths: list[str]) -> list[str]:
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
        packages = workspaces.member_dirs(paths, members, "pyproject.toml")
    else:
        packages = [""] if isinstance(data.get("project"), dict) else []
    return [package for package in packages if ctx.config.source_oracle.classify_directory(package).needs_tests]


def _needs_story_tests(package: str, repo: Repo, ctx: Context, paths: list[str]) -> bool:
    manifest_path = f"{package}/pyproject.toml" if package else "pyproject.toml"
    content = ctx.file(repo, manifest_path)
    if content is not None:
        try:
            project = tomllib.loads(content).get("project")
        except tomllib.TOMLDecodeError:
            project = None
        if isinstance(project, dict) and project.get("scripts"):
            return True
    return any(under_package(path, package) and PY_TEST.fullmatch(path.rsplit("/", 1)[-1]) for path in paths)


def list_python_stories(package: str, paths: list[str]) -> list[str]:
    return [path for path in paths if under_package(path, package) and PY_STORY.fullmatch(path.rsplit("/", 1)[-1])]


def _list_python_docs(repo: Repo, ctx: Context, paths: list[str], tests: list[str]) -> dict[str, str]:
    test_dirs = {path.rpartition("/")[0] for path in tests}
    docs: dict[str, str] = {}
    for path in paths:
        directory, _, name = path.rpartition("/")
        if not name.endswith(".md") or (content := ctx.file(repo, path)) is None:
            continue
        target = find_title_target(content)
        if PY_TEST.fullmatch(target) or (
            not TS_TEST.fullmatch(target)
            and _DOC_NAME.fullmatch(name)
            and (directory in test_dirs or _PY_DOC_NAME.fullmatch(name))
        ):
            docs[path] = content
    return docs


def _headers_of(res: CheckResult, group: _Group) -> dict[str, Header]:
    headers: dict[str, Header] = {}
    for path, content in group.docs.items():
        for header in _iter_headers(content):
            if header.story_id in headers:
                res.fail(f"{path}: duplicate story criterion {header.story_id}")
            headers[header.story_id] = header
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
            res.fail(
                f"{group.directory}: header/test title drift for {story_id} — "
                f"header={header_title!r} test={test_title!r}"
            )


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
    headers = _headers_of(res, group)
    for section in {story_id.split(".")[0] for story_id in group.tests}:
        if len({test.file for test in group.tests.values() if test.story_id.startswith(f"{section}.")}) > 1:
            res.fail(f"{group.directory}: section {section} occurs in multiple story test files")
    if group.docs and not headers:
        res.fail(f"{group.directory}: no numbered story criteria")
    _check_presence(res, group, headers)
    _check_title_drift(res, group, headers)
    _check_own_section(res, group)
    _check_header_links(res, ctx, repo, group)


def run_story_check(repo: Repo, ctx: Context, res: CheckResult) -> None:
    paths = ctx.paths(repo)
    packages = list_python_packages(repo, ctx, paths)
    if not packages:
        res.skip("no Python packages")
        return

    sources = list_story_sources(repo, ctx)
    did_check = False
    for package in sorted(packages):
        tests = list_python_stories(package, sources)
        docs = _list_python_docs(repo, ctx, [path for path in sources if under_package(path, package)], tests)
        directories = {path.rpartition("/")[0] for path in (*docs, *tests)}
        if not directories:
            if _needs_story_tests(package, repo, ctx, paths):
                res.fail(f"{package or '.'}: exposes a public interface but has no user-story tests")
                did_check = True
            continue

        did_check = True
        for directory in sorted(directories):
            local_docs = {path: content for path, content in docs.items() if path.rpartition("/")[0] == directory}
            local_tests = _collect_tests(
                repo, ctx, res, [path for path in tests if path.rpartition("/")[0] == directory]
            )
            _check_group(res, ctx, repo, _Group(directory, local_docs, local_tests))

    if not did_check:
        res.skip("no Python package needs story-based tests")
    elif not res.problems:
        res.ok("every story criterion has a matching, title-matched test")
