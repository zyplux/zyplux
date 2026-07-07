"""Meta-test: numbered story docs' h3 headers and tests/stories test functions stay in lockstep; each h1 doc title links to its section's test file."""

from project_paths import list_story_docs
from sync_story_links import Header, collect_story_tests, parse_headers, render_linked_doc


def collect_headers() -> dict[str, Header]:
    headers: dict[str, Header] = {}
    for doc_path in list_story_docs():
        headers.update(parse_headers(doc_path.read_text(encoding="utf-8")))
    return headers


def test_every_story_test_has_a_header() -> None:
    orphans = sorted(set(collect_story_tests()) - set(collect_headers()))
    assert not orphans, "story tests with no matching ### header in the story docs: " + ", ".join(orphans)


def test_every_header_has_a_story_test() -> None:
    orphans = sorted(set(collect_headers()) - set(collect_story_tests()))
    assert not orphans, "### story-doc headers with no matching story test: " + ", ".join(orphans)


def word_sequence(title: str) -> list[str]:
    (
        """A title's comparable words. A header's prose may join words with a hyphen ("non-interactive") that the test name can only spell as separate """
        """underscore tokens ("non interactive"), so treat a hyphen as the same word break — without it the two spellings read as drift."""
    )
    return title.replace("-", " ").split()


def test_header_titles_match_test_names() -> None:
    tests = collect_story_tests()
    headers = collect_headers()
    drifted = {
        sid: (headers[sid].title, tests[sid].title) for sid in set(tests) & set(headers) if word_sequence(headers[sid].title) != word_sequence(tests[sid].title)
    }
    assert not drifted, f"header title vs test-name drift (id: header, test): {drifted}"


def test_each_doc_holds_only_its_own_section() -> None:
    strays = {
        doc_path.name: sorted({header for header in parse_headers(doc_path.read_text(encoding="utf-8")) if header.split(".")[0] != doc_path.name.split("_")[0]})
        for doc_path in list_story_docs()
    }
    strays = {name: ids for name, ids in strays.items() if ids}
    assert not strays, f"story headers filed in the wrong section doc: {strays}"


def test_every_header_links_to_its_test() -> None:
    tests = collect_story_tests()
    docs = {doc_path.name: doc_path.read_text(encoding="utf-8") for doc_path in list_story_docs()}
    stale = [name for name, doc in docs.items() if doc != render_linked_doc(doc, tests)]
    assert not stale, "story header links are stale — run `just lint` to refresh them: " + ", ".join(stale)


def test_render_linked_doc_is_a_fixed_point() -> None:
    tests = collect_story_tests()
    for doc_path in list_story_docs():
        linked = render_linked_doc(doc_path.read_text(encoding="utf-8"), tests)
        assert linked == render_linked_doc(linked, tests), f"render_linked_doc keeps rewriting its own output for {doc_path.name}"
