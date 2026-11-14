from __future__ import annotations

import re
from collections import Counter
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from cerberus.bites.story_files import PY_TEST, TS_TEST, find_title_target, list_story_sources
from cerberus.graph.parse import parse_typescript
from cerberus.ts_syntax import node_text, string_literal, walk_nodes

if TYPE_CHECKING:
    from tree_sitter import Node

    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo

_ID = re.compile(r"^([a-zA-Z0-9]*\d+(?:\.\d+)+)\b")
_HEADER = re.compile(
    r"^#{2,6} ([a-zA-Z0-9]*\d+(?:\.\d+)+)(?:[\u2013-]([a-zA-Z0-9]*\d+(?:\.\d+)+))? (.+)$", re.MULTILINE
)
_TITLE = re.compile(r"^# ([a-zA-Z0-9]*\d+)\. (.+)$", re.MULTILINE)


def _find_table(call: Node, name: str) -> Node | None:
    parent = call.parent
    while parent is not None:
        for declaration in parent.named_children:
            if declaration.type != "lexical_declaration":
                continue
            for binding in declaration.named_children:
                identifier = binding.child_by_field_name("name")
                value = binding.child_by_field_name("value")
                if (
                    identifier is not None
                    and node_text(identifier) == name
                    and value is not None
                    and value.type == "array"
                ):
                    return value
        parent = parent.parent
    return None


def _test_titles(call: Node) -> list[str]:
    function = call.child_by_field_name("function")
    arguments = call.child_by_field_name("arguments")
    if function is None or arguments is None or not arguments.named_children:
        return []
    root = node_text(function).split(".", 1)[0].strip()
    if root not in {"test", "it"}:
        return []
    title = string_literal(arguments.named_children[0])
    if title is None:
        return []
    if "%s" not in title.split(" ", 1)[0]:
        return [title]
    arrays = [node for node in walk_nodes(function) if node.type == "array"]
    if not arrays:
        arrays = [
            table
            for node in walk_nodes(function)
            if node.type == "identifier" and (table := _find_table(call, node_text(node))) is not None
        ]
    if not arrays:
        return []
    titles = []
    for row in arrays[0].named_children:
        cell = row.named_children[0] if row.type == "array" and row.named_children else row
        label = string_literal(cell)
        if label is not None:
            titles.append(title.replace("%s", label, 1))
    return titles


def _test_ids(path: str, content: str) -> list[str]:
    ids = []
    root = parse_typescript(path, content).root_node
    for node in walk_nodes(root):
        if node.type != "call_expression":
            continue
        titles = _test_titles(node)
        matches = [match.group(1) for title in titles if (match := _ID.match(title)) is not None]
        ids.extend(dict.fromkeys(matches))
    return ids


def _expand_heading(header: re.Match[str]) -> list[str]:
    first, last = header.group(1, 2)
    if last is None:
        return [first]
    first_group, first_number = first.rsplit(".", 1)
    last_group, last_number = last.rsplit(".", 1)
    if first_group != last_group or int(last_number) < int(first_number):
        message = f"criterion range {first}-{last} must ascend within one group"
        raise ValueError(message)
    return [f"{first_group}.{number}" for number in range(int(first_number), int(last_number) + 1)]


def _criteria(content: str) -> list[str]:
    headings = []
    parent = ""
    is_list_criteria = False
    for line in content.splitlines():
        header = _HEADER.fullmatch(line)
        if header is not None:
            parent = header.group(1)
            is_list_criteria = line.startswith("## ") and header.group(2) is None
            headings.extend(_expand_heading(header))
        elif line.startswith("#"):
            parent = ""
            is_list_criteria = False
        item = re.match(r"^(\d+)\. ", line)
        if item is not None and parent and is_list_criteria:
            headings.append(f"{parent}.{item.group(1)}")
    return [heading for heading in headings if not any(other.startswith(f"{heading}.") for other in headings)]


def _render_title(title: re.Match[str], files: dict[str, str]) -> str:
    section, label = title.group(1, 2)
    plain = re.sub(r"^\[(.+)\]\([^)]+\)$", r"\1", label)
    return f"# {section}. [{plain}]({files[section]})"


def _check_doc(repo: Repo, ctx: Context, res: CheckResult, path: str, files: dict[str, str]) -> list[str]:
    content = ctx.file(repo, path) or ""
    try:
        criteria = _criteria(content)
    except ValueError as err:
        res.fail(f"{path}: {err}")
        return []
    if not criteria:
        res.fail(f"{path}: no numbered or prefixed story criteria")
    title = _TITLE.search(content)
    if title is None:
        target = find_title_target(content)
        if target and target not in files.values():
            res.fail(f"{path}: story title links to an unmatched test: {target}")
        return criteria
    section = title.group(1)
    misplaced = [criterion for criterion in criteria if not criterion.startswith(f"{section}.")]
    if misplaced:
        res.fail(f"{path}: story criteria filed in the wrong section doc: {', '.join(misplaced)}")
    if section in files and (linked := _render_title(title, files)) != title.group():
        if ctx.fix:
            ctx.write_file(repo, path, content[: title.start()] + linked + content[title.end() :])
        else:
            res.fail(f"{path}: story header links are stale; run with --fix")
    return criteria


def _check_ids(directory: str, criteria: list[str], test_ids: list[str], res: CheckResult) -> None:
    for label, ids in (("story criteria", criteria), ("test IDs", test_ids)):
        duplicates = sorted(story_id for story_id, count in Counter(ids).items() if count > 1)
        if duplicates:
            res.fail(f"{directory}: duplicate {label}: {', '.join(duplicates)}")
    for label, missing in (
        ("story criteria without tests", set(criteria) - set(test_ids)),
        ("tests without story criteria", set(test_ids) - set(criteria)),
    ):
        if missing:
            res.fail(f"{directory}: {label}: {', '.join(sorted(missing))}")
    if not criteria and not test_ids:
        res.fail(f"{directory}: story tests require numbered or prefixed criterion IDs and documentation")


def _list_docs(repo: Repo, ctx: Context, paths: list[str]) -> dict[str, str]:
    docs: dict[str, str] = {}
    for path in paths:
        if not path.endswith(".md"):
            continue
        content = ctx.file(repo, path) or ""
        target = find_title_target(content)
        if TS_TEST.fullmatch(target) or (not PY_TEST.fullmatch(target) and _HEADER.search(content)):
            docs[path] = target
    return docs


def _get_sections(res: CheckResult, tests: dict[str, list[str]]) -> dict[str, str]:
    files: dict[str, str] = {}
    for path, ids in tests.items():
        name = PurePosixPath(path).name
        for section in {story_id.split(".", 1)[0] for story_id in ids}:
            if section in files and files[section] != name:
                res.fail(f"{path}: section {section} occurs in multiple story test files")
            files[section] = name
    return files


def _check_group(repo: Repo, ctx: Context, res: CheckResult, directory: str, paths: list[str]) -> int:
    docs = _list_docs(repo, ctx, paths)
    linked = set(docs.values())
    tests = {
        path: ids
        for path in paths
        if TS_TEST.fullmatch(PurePosixPath(path).name)
        and ((ids := _test_ids(path, ctx.file(repo, path) or "")) or PurePosixPath(path).name in linked)
    }
    for path, ids in tests.items():
        if not ids:
            res.fail(f"{path}: no numbered or prefixed story test IDs")
    if tests or docs:
        files = _get_sections(res, tests)
        criteria = [criterion for path in docs for criterion in _check_doc(repo, ctx, res, path, files)]
        _check_ids(directory, criteria, [story_id for ids in tests.values() for story_id in ids], res)
    return len(tests)


def run_story_check(repo: Repo, ctx: Context, res: CheckResult) -> None:
    groups: dict[str, list[str]] = {}
    for path in list_story_sources(repo, ctx):
        if PY_TEST.fullmatch(PurePosixPath(path).name):
            continue
        groups.setdefault(PurePosixPath(path).parent.as_posix(), []).append(path)
    checked = sum(_check_group(repo, ctx, res, directory, paths) for directory, paths in sorted(groups.items()))
    if not res.problems:
        if checked:
            res.ok(f"{checked} TypeScript story files pair with criteria in their own directories")
        else:
            res.skip("no documented TypeScript story directories")
