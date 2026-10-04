from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from seam_fixtures import RunCheckWithFiles


@pytest.mark.parametrize("prefix", ["1", "smb1", "e2e4"])
def test_35_1_1_pairs_prefixed_or_numeric_ids_in_shared_domain_suites(
    run_check_with_files: RunCheckWithFiles, prefix: str
) -> None:
    files = {
        "tests/smoke/stories/module-boundaries/story.md": f"## {prefix}.1 a criterion\n",
        "tests/smoke/stories/module-boundaries/story.test.ts": f'test("{prefix}.1 different prose", () => {{}});',
    }
    assert not run_check_with_files("story_tests_lockstep_ts", files).problems


def test_35_1_2_pairs_colocated_ui_stories_without_product_basename_assumptions(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    files = {
        "apps/dashboard/tests/stories/1-ui.md": "## 1.1 rendering\n### 1.1.1 renders a button\n",
        "apps/dashboard/tests/stories/1-ui.test.ts": 'test("1.1.1 renders a button", () => {});',
    }
    assert not run_check_with_files("story_tests_lockstep_ts", files).problems


def test_35_1_3_leaves_ordinary_infrastructure_tests_outside_story_pairing(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    assert not run_check_with_files(
        "story_tests_lockstep_ts", {"infra/worker/router.test.ts": 'test("routes a request", () => {});'}
    ).problems


@pytest.mark.parametrize(
    ("doc", "source"),
    [
        ("## 1.1 criterion\n## 1.1 duplicate\n", 'test("1.1 criterion", () => {});'),
        ("## 1.1 criterion\n", 'test("1.1 criterion", () => {}); test("1.1 duplicate", () => {});'),
        ("## 1.2 absent\n", 'test("1.1 criterion", () => {});'),
        ("", 'test("unnumbered", () => {});'),
    ],
)
def test_35_2_1_rejects_duplicate_or_unpaired_criteria_before_building_lookups(
    run_check_with_files: RunCheckWithFiles, doc: str, source: str
) -> None:
    assert run_check_with_files(
        "story_tests_lockstep_ts",
        {"tests/e2e/stories/api/story.md": doc, "tests/e2e/stories/api/story.test.ts": source},
    ).problems


def test_35_2_2_resolves_scoped_tables_and_ignores_test_like_comments_or_strings(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    source = """describe("group", () => { const cases = [["1 first"], ["2 second"]];
test.for(cases)("1.1.%s", () => {}); });
describe("other", () => { const cases = [["1 third"]]; test.for(cases)("1.2.%s", () => {}); });
// test("9.9 bogus", () => {});
const text = 'test("9.8 bogus", () => {})';"""
    files = {
        "tests/e2e/stories/api/story.md": "## 1.1 group\n1. first\n2. second\n## 1.2 other\n1. third\n",
        "tests/e2e/stories/api/story.test.ts": source,
    }
    assert not run_check_with_files("story_tests_lockstep_ts", files).problems


def test_35_2_3_rejects_criteria_in_the_wrong_document_and_split_sections(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    files = {
        "tests/stories/api/first.md": "# 1. first\n## 2.1 misplaced\n",
        "tests/stories/api/first.test.ts": 'test("2.1 misplaced", () => {});',
    }
    assert run_check_with_files("story_tests_lockstep_ts", files).problems
    files["tests/stories/api/first.md"] = "## 2.1 first\n## 2.2 second\n"
    files["tests/stories/api/second.test.ts"] = 'test("2.2 second", () => {});'
    assert run_check_with_files("story_tests_lockstep_ts", files).problems


def test_35_2_4_distinguishes_criterion_lists_from_prose_under_an_unnumbered_heading(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    files = {
        "tests/stories/api/story.md": "## 1.1 criterion\n### Implementation details\n1. an example step\n",
        "tests/stories/api/story.test.ts": 'test("1.1 criterion", () => {});',
    }
    assert not run_check_with_files("story_tests_lockstep_ts", files).problems


@pytest.mark.parametrize("separator", ["\u2013", "-"])
def test_35_1_4_pairs_grouped_criterion_ranges(
    run_check_with_files: RunCheckWithFiles,
    separator: str,
) -> None:
    files = {
        "tests/stories/api/story.md": f"## 4.3{separator}4.5 duplicate files\n",
        "tests/stories/api/story.test.ts": (
            'test("4.3 workflow", () => {});test("4.4 tool", () => {});test("4.5 connector", () => {});'
        ),
    }
    assert not run_check_with_files("story_tests_lockstep_ts", files).problems
