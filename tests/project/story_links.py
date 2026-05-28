"""Links each h3 story header to its section's test file; h4 criterion headers stay plain but track tests by id. Run as a script to refresh the links."""

import ast
import re
from dataclasses import dataclass

from project_paths import STORIES_DIR, STORIES_DOC

H3_HEADER = re.compile(r"^### (\d+\.\d+) (.+)$")
H4_HEADER = re.compile(r"^#### (\d+(?:\.\d+)+) (.+)$")
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
        for node in ast.parse(path.read_text()).body:
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
        header = H4_HEADER.match(line)
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
        h3 = H3_HEADER.match(stripped)
        h4 = H4_HEADER.match(stripped)
        if h3:
            story_id, title = h3.group(1), strip_link(h3.group(2))
            file = files.get(story_id.split(".")[0])
            rendered.append(raw if file is None else f"### {story_id} [{title}]({file}){newline}")
        elif h4:
            story_id, title = h4.group(1), strip_link(h4.group(2))
            rendered.append(f"#### {story_id} {title}{newline}")
        else:
            rendered.append(raw)
    return "".join(rendered)


def sync_links() -> bool:
    doc = STORIES_DOC.read_text()
    relinked = render_linked_doc(doc, collect_story_tests())
    if relinked != doc:
        STORIES_DOC.write_text(relinked)
    return relinked != doc


if __name__ == "__main__":
    print("user-stories.md links refreshed" if sync_links() else "user-stories.md links already current")
