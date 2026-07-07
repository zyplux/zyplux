"""Meta-test: the numbered story docs' h3 criterion headers and the tests/stories test functions stay in lockstep, each h1 doc title linked to its section's test file."""

from project_paths import list_story_docs
from sync_story_links import collect_story_tests, parse_headers, render_linked_doc


def collect_headers():
    headers = {}
    for doc_path in list_story_docs():
        headers.update(parse_headers(doc_path.read_text()))
    return headers


def test_every_story_test_has_a_header():
    orphans = sorted(set(collect_story_tests()) - set(collect_headers()))
    assert not orphans, "story tests with no matching ### header in the story docs: " + ", ".join(orphans)


def test_every_header_has_a_story_test():
    orphans = sorted(set(collect_headers()) - set(collect_story_tests()))
    assert not orphans, "### story-doc headers with no matching story test: " + ", ".join(orphans)


def word_sequence(title: str) -> list[str]:
    """A title's comparable words. A header's prose may join words with a hyphen ("non-interactive") that the test name can only spell as separate underscore tokens ("non interactive"), so treat a hyphen as the same word break — without it the two spellings read as drift."""
    return title.replace("-", " ").split()


def test_header_titles_match_test_names():
    tests = collect_story_tests()
    headers = collect_headers()
    drifted = {
        sid: (headers[sid].title, tests[sid].title) for sid in set(tests) & set(headers) if word_sequence(headers[sid].title) != word_sequence(tests[sid].title)
    }
    assert not drifted, f"header title vs test-name drift (id: header, test): {drifted}"


def test_each_doc_holds_only_its_own_section():
    strays = {
        doc_path.name: sorted({header for header in parse_headers(doc_path.read_text()) if header.split(".")[0] != doc_path.name.split("_")[0]})
        for doc_path in list_story_docs()
    }
    strays = {name: ids for name, ids in strays.items() if ids}
    assert not strays, f"story headers filed in the wrong section doc: {strays}"


def test_every_header_links_to_its_test():
    tests = collect_story_tests()
    stale = [doc_path.name for doc_path in list_story_docs() if doc_path.read_text() != render_linked_doc(doc_path.read_text(), tests)]
    assert not stale, "story header links are stale — run `just lint` to refresh them: " + ", ".join(stale)


def test_render_linked_doc_is_a_fixed_point():
    tests = collect_story_tests()
    for doc_path in list_story_docs():
        linked = render_linked_doc(doc_path.read_text(), tests)
        assert linked == render_linked_doc(linked, tests), f"render_linked_doc keeps rewriting its own output for {doc_path.name}"
