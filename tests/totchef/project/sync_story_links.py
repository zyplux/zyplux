(
    """Derives story-doc header links from tests/stories: h1 links to its test file, h2/h3 stay plain; """
    """`just lint` runs this to refresh stale links."""
)

import ast
import re
import sys
from dataclasses import dataclass

from project_paths import STORIES_DIR, list_story_docs

DOC_TITLE = re.compile(r"^# (\d+)\. (.+)$")
STORY_HEADER = re.compile(r"^## (\d+\.\d+) (.+)$")
CRITERION_HEADER = re.compile(r"^### (\d+(?:\.\d+)+) (.+)$")
LINKED_TITLE = re.compile(r"^\[(?P<title>.+)\]\((?P<target>[^)]+)\)$")


@dataclass(frozen=True)
class StoryTest:
    story_id: str
    title: str
    file: str


@dataclass(frozen=True)
class Header:
    story_id: str
    title: str
    target: str | None


def split_id_and_title(func_name: str) -> tuple[str, str]:
    tokens = func_name.removeprefix("test_").split("_")
    cut = 0
    while cut < len(tokens) and tokens[cut].isdigit():
        cut += 1
    return ".".join(tokens[:cut]), " ".join(tokens[cut:])


def collect_story_tests() -> dict[str, StoryTest]:
    tests: dict[str, StoryTest] = {}
    for path in sorted(STORIES_DIR.glob("test_[0-9]*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                story_id, title = split_id_and_title(node.name)
                if story_id:
                    tests[story_id] = StoryTest(story_id, title, path.name)
    return tests


def section_files(tests: dict[str, StoryTest]) -> dict[str, str]:
    return {test.story_id.split(".")[0]: test.file for test in tests.values()}


def strip_link(rest: str) -> str:
    linked = LINKED_TITLE.match(rest)
    return linked.group("title") if linked else rest


def parse_headers(doc: str) -> dict[str, Header]:
    headers: dict[str, Header] = {}
    for line in doc.splitlines():
        header = CRITERION_HEADER.match(line)
        if not header:
            continue
        story_id, rest = header.group(1), header.group(2)
        linked = LINKED_TITLE.match(rest)
        if linked:
            headers[story_id] = Header(story_id, linked.group("title"), linked.group("target"))
        else:
            headers[story_id] = Header(story_id, rest, None)
    return headers


def render_linked_doc(doc: str, tests: dict[str, StoryTest]) -> str:
    files = section_files(tests)
    rendered: list[str] = []
    for raw in doc.splitlines(keepends=True):
        stripped = raw.rstrip("\n")
        newline = raw[len(stripped) :]
        doc_title = DOC_TITLE.match(stripped)
        story = STORY_HEADER.match(stripped)
        criterion = CRITERION_HEADER.match(stripped)
        if doc_title:
            section, title = doc_title.group(1), strip_link(doc_title.group(2))
            file = files.get(section)
            rendered.append(raw if file is None else f"# {section}. [{title}]({file}){newline}")
        elif story:
            story_id, title = story.group(1), strip_link(story.group(2))
            rendered.append(f"## {story_id} {title}{newline}")
        elif criterion:
            story_id, title = criterion.group(1), strip_link(criterion.group(2))
            rendered.append(f"### {story_id} {title}{newline}")
        else:
            rendered.append(raw)
    return "".join(rendered)


def sync_links() -> list[str]:
    tests = collect_story_tests()
    refreshed: list[str] = []
    for doc_path in list_story_docs():
        doc = doc_path.read_text(encoding="utf-8")
        relinked = render_linked_doc(doc, tests)
        if relinked != doc:
            doc_path.write_text(relinked, encoding="utf-8")
            refreshed.append(doc_path.name)
    return refreshed


if __name__ == "__main__":
    refreshed = sync_links()
    sys.stdout.write((f"links refreshed: {', '.join(refreshed)}" if refreshed else "story links fresh") + "\n")
