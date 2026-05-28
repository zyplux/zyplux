"""Meta-test: the user-stories.md h4 headers and the tests/stories test functions stay in lockstep, each h3 story header linked to its section's test file."""

from project_paths import STORIES_DOC
from story_links import collect_story_tests, parse_headers, render_linked_doc


def test_every_story_test_has_a_header():
    tests = collect_story_tests()
    headers = parse_headers(STORIES_DOC.read_text())
    orphans = sorted(set(tests) - set(headers))
    assert not orphans, "story tests with no matching #### header in user-stories.md: " + ", ".join(orphans)


def test_every_header_has_a_story_test():
    tests = collect_story_tests()
    headers = parse_headers(STORIES_DOC.read_text())
    orphans = sorted(set(headers) - set(tests))
    assert not orphans, "#### headers in user-stories.md with no matching story test: " + ", ".join(orphans)


def test_header_titles_match_test_names():
    tests = collect_story_tests()
    headers = parse_headers(STORIES_DOC.read_text())
    drifted = {sid: (headers[sid].title, tests[sid].title) for sid in set(tests) & set(headers) if headers[sid].title != tests[sid].title}
    assert not drifted, f"header title vs test-name drift (id: header, test): {drifted}"


def test_every_header_links_to_its_test():
    doc = STORIES_DOC.read_text()
    assert doc == render_linked_doc(doc, collect_story_tests()), (
        "story header links are stale — run `uv run python tests/project/story_links.py` to refresh them (or `just lint`)"
    )
