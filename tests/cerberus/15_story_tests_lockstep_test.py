# @story
from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from seam_fixtures import MakeFinding, RunCheckOnDisk, RunCheckWithFiles


PY_CHECK_ID = "story_tests_lockstep_py"

DOC = (
    "# 1. Configuring a widget\n\n## 1.1 Widget setup\n\n"
    "### 1.1.1 shows the widget name\n\n### 1.1.2 accepts a custom color\n"
)
DOC_PATH = "tests/stories/1_widget.md"

PY_TEST_PATH = "tests/stories/1_widget_test.py"
PY_TEST = """# @story
def test_1_1_1_shows_the_widget_name():
    pass


def test_1_1_2_accepts_a_custom_color():
    pass
"""


_PY_PLAIN_PYPROJECT = '[project]\nname = "widget"\n'
_PY_SCRIPTS_PYPROJECT = '[project]\nname = "widget"\n\n[project.scripts]\nwidget = "widget.cli:main"\n'
_PY_UV_WORKSPACE_APPS = '[tool.uv.workspace]\nmembers = ["apps/*"]\n'


OK_MESSAGE = "every story criterion has a matching, title-matched test"
NO_MATCHING_TEST_HEADER_MESSAGE = "tests/stories: story-doc ### header(s) with no matching test: 1.1.2"
PY_STALE_LINK_MESSAGE = "tests/stories/1_widget.md: story header links are stale; run with --fix"
TITLE_DRIFT_MESSAGE = (
    "tests/stories: header/test title drift for 1.1.1 — header='shows the widget name' test='shows a different name'"
)


def _needs_story_tests_message(package: str) -> str:
    return f"{package}: exposes a public interface but has no user-story tests"


NEEDS_STORY_TESTS_MESSAGE = _needs_story_tests_message(".")


def _linked(target: str) -> str:
    return DOC.replace("# 1. Configuring a widget\n", f"# 1. [Configuring a widget]({target})\n")


def test_15_1_1_skips_a_repo_with_no_python_packages_at_all(
    run_check_with_files: RunCheckWithFiles, skip: MakeFinding
) -> None:
    result = run_check_with_files(PY_CHECK_ID, {"README.md": "# demo\n"})
    assert result.findings == [skip("no Python packages")]


def test_15_1_3_ignores_a_directory_outside_the_workspace_glob(
    run_check_with_files: RunCheckWithFiles, skip: MakeFinding
) -> None:
    files = {"pyproject.toml": _PY_UV_WORKSPACE_APPS, "libs/other/pyproject.toml": _PY_SCRIPTS_PYPROJECT}
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [skip("no Python packages")]


def test_15_2_1_fails_a_python_package_that_exposes_a_cli_script_but_has_no_story_tests(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    result = run_check_with_files(PY_CHECK_ID, {"pyproject.toml": _PY_SCRIPTS_PYPROJECT})
    assert result.findings == [fail(NEEDS_STORY_TESTS_MESSAGE)]


def test_15_2_3_skips_a_python_package_with_no_public_interface_and_no_tests(
    run_check_with_files: RunCheckWithFiles, skip: MakeFinding
) -> None:
    result = run_check_with_files(PY_CHECK_ID, {"pyproject.toml": _PY_PLAIN_PYPROJECT})
    assert result.findings == [skip("no Python package needs story-based tests")]


def test_15_2_5_fails_a_python_package_that_already_has_plain_tests_but_no_story_docs(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {"pyproject.toml": _PY_PLAIN_PYPROJECT, "tests/test_widget.py": "def test_it():\n    pass\n"}
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [fail(NEEDS_STORY_TESTS_MESSAGE)]


def test_15_3_1_passes_a_python_workspace_member_with_colocated_story_tests(
    run_check_with_files: RunCheckWithFiles, ok: MakeFinding
) -> None:
    files = {
        "pyproject.toml": _PY_UV_WORKSPACE_APPS,
        "apps/widget/pyproject.toml": _PY_SCRIPTS_PYPROJECT,
        "apps/widget/components/widget.md": _linked("1_widget_test.py"),
        "apps/widget/components/1_widget_test.py": PY_TEST,
    }
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [ok(OK_MESSAGE)]


class StaleHeaderCase(NamedTuple):
    check_id: str
    files: dict[str, str]
    stale_link_message: str


_NO_MATCHING_TEST_CASES = [
    StaleHeaderCase(
        PY_CHECK_ID,
        {
            "pyproject.toml": _PY_PLAIN_PYPROJECT,
            DOC_PATH: DOC,
            PY_TEST_PATH: "# @story\ndef test_1_1_1_shows_the_widget_name():\n    pass\n",
        },
        PY_STALE_LINK_MESSAGE,
    ),
]


@pytest.mark.parametrize("case", _NO_MATCHING_TEST_CASES, ids=["python"])
def test_15_4_1_flags_a_story_header_with_no_matching_test(
    run_check_with_files: RunCheckWithFiles, case: StaleHeaderCase, fail: MakeFinding
) -> None:
    result = run_check_with_files(case.check_id, case.files)
    assert result.findings == [
        fail(NO_MATCHING_TEST_HEADER_MESSAGE),
        fail(case.stale_link_message),
    ]


def test_15_4_2_flags_a_test_with_no_matching_story_header(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {
        "pyproject.toml": _PY_PLAIN_PYPROJECT,
        DOC_PATH: "# 1. Configuring a widget\n\n### 1.1.1 shows the widget name\n",
        PY_TEST_PATH: PY_TEST,
    }
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [
        fail("tests/stories: story test(s) with no matching ### header: 1.1.2"),
        fail(PY_STALE_LINK_MESSAGE),
    ]


_TITLE_DRIFT_CASES = [
    StaleHeaderCase(
        PY_CHECK_ID,
        {
            "pyproject.toml": _PY_PLAIN_PYPROJECT,
            DOC_PATH: DOC,
            PY_TEST_PATH: PY_TEST.replace("shows_the_widget_name", "shows_a_different_name"),
        },
        PY_STALE_LINK_MESSAGE,
    ),
]


@pytest.mark.parametrize("case", _TITLE_DRIFT_CASES, ids=["python"])
def test_15_4_3_flags_a_title_that_has_drifted_between_the_header_and_its_test(
    run_check_with_files: RunCheckWithFiles, case: StaleHeaderCase, fail: MakeFinding
) -> None:
    result = run_check_with_files(case.check_id, case.files)
    assert result.findings == [
        fail(TITLE_DRIFT_MESSAGE),
        fail(case.stale_link_message),
    ]


def test_15_4_4_flags_a_criterion_filed_under_the_wrong_section_doc(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {
        "pyproject.toml": _PY_PLAIN_PYPROJECT,
        DOC_PATH: DOC.replace("### 1.1.2", "### 2.1.2"),
        PY_TEST_PATH: PY_TEST.replace("test_1_1_2", "test_2_1_2"),
    }
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [
        fail("tests/stories/1_widget.md: story header(s) filed in the wrong section doc: 2.1.2"),
        fail(PY_STALE_LINK_MESSAGE),
    ]


def test_15_4_5_does_not_flag_titles_that_differ_only_by_punctuation_or_case(
    run_check_with_files: RunCheckWithFiles, ok: MakeFinding
) -> None:
    files = {
        "pyproject.toml": _PY_PLAIN_PYPROJECT,
        DOC_PATH: _linked("1_widget_test.py").replace("shows the widget name", "shows the widget's fileName.txt"),
        PY_TEST_PATH: PY_TEST.replace("test_1_1_1_shows_the_widget_name", "test_1_1_1_shows_the_widgets_file_name_txt"),
    }
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [ok(OK_MESSAGE)]


def test_15_5_1_flags_a_stale_header_link(run_check_with_files: RunCheckWithFiles, fail: MakeFinding) -> None:
    files = {
        "pyproject.toml": _PY_PLAIN_PYPROJECT,
        DOC_PATH: DOC.replace("# 1. Configuring a widget\n", "# 1. [Configuring a widget](test_wrong_file.py)\n"),
        PY_TEST_PATH: PY_TEST,
    }
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [fail(PY_STALE_LINK_MESSAGE)]


class StaleLinkCase(NamedTuple):
    manifest_name: str
    manifest_content: str
    test_name: str
    test_content: str
    linked_target: str
    doc_name: str
    check_id: str


_STALE_LINK_CASES = [
    StaleLinkCase(
        "pyproject.toml",
        _PY_PLAIN_PYPROJECT,
        "1_widget_test.py",
        PY_TEST,
        "1_widget_test.py",
        "1_widget.md",
        PY_CHECK_ID,
    ),
]


@pytest.mark.parametrize("case", _STALE_LINK_CASES, ids=["python"])
def test_15_5_2_rewrites_a_stale_header_link_and_passes_on_the_next_run(
    run_check_on_disk: RunCheckOnDisk, tmp_path: Path, case: StaleLinkCase, ok: MakeFinding
) -> None:
    files = {
        case.manifest_name: case.manifest_content,
        f"tests/stories/{case.doc_name}": DOC,
        f"tests/stories/{case.test_name}": case.test_content,
    }
    run_check_on_disk(case.check_id, files, fix=True)
    doc_path = tmp_path / "tests" / "stories" / case.doc_name
    assert f"[Configuring a widget]({case.linked_target})" in doc_path.read_text()

    result = run_check_on_disk(case.check_id, {}, fix=False)
    assert result.findings == [ok(OK_MESSAGE)]


def test_15_5_3_flags_a_linked_criterion_header_for_unlinking(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {
        "pyproject.toml": _PY_PLAIN_PYPROJECT,
        DOC_PATH: _linked("1_widget_test.py").replace(
            "### 1.1.1 shows the widget name",
            "### 1.1.1 [shows the widget name](1_widget_test.py)",
        ),
        PY_TEST_PATH: PY_TEST,
    }
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [fail(PY_STALE_LINK_MESSAGE)]


def test_15_5_4_leaves_a_freshly_linked_doc_unchanged_on_a_fix_rerun(
    run_check_on_disk: RunCheckOnDisk, tmp_path: Path, ok: MakeFinding
) -> None:
    files = {
        "pyproject.toml": _PY_PLAIN_PYPROJECT,
        DOC_PATH: DOC,
        PY_TEST_PATH: PY_TEST,
    }
    run_check_on_disk(PY_CHECK_ID, files, fix=True)
    doc_path = tmp_path / "tests" / "stories" / "1_widget.md"
    linked_doc = doc_path.read_text()

    result = run_check_on_disk(PY_CHECK_ID, {}, fix=True)
    assert doc_path.read_text() == linked_doc
    assert result.findings == [ok(OK_MESSAGE)]


def test_15_3_3_passes_a_workspace_member_with_torn_out_story_tests(
    run_check_with_files: RunCheckWithFiles, ok: MakeFinding
) -> None:
    files = {
        "pyproject.toml": _PY_UV_WORKSPACE_APPS,
        "apps/widget/pyproject.toml": _PY_SCRIPTS_PYPROJECT,
        "tests/widget/1_widget.md": _linked("1_widget_test.py"),
        "tests/widget/1_widget_test.py": PY_TEST,
    }
    assert run_check_with_files(PY_CHECK_ID, files).findings == [ok(OK_MESSAGE)]


def test_15_8_1_checks_each_domain_independently(run_check_with_files: RunCheckWithFiles, ok: MakeFinding) -> None:
    files = {"pyproject.toml": _PY_SCRIPTS_PYPROJECT}
    for domain in ("api", "workflows"):
        files[f"tests/stories/{domain}/1_widget.md"] = _linked("1_widget_test.py")
        files[f"tests/stories/{domain}/1_widget_test.py"] = PY_TEST
    assert run_check_with_files(PY_CHECK_ID, files).findings == [ok(OK_MESSAGE)]


def test_15_8_2_does_not_pair_story_criteria_across_workspace_owners(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {
        "pyproject.toml": _PY_UV_WORKSPACE_APPS,
        "apps/widget/pyproject.toml": _PY_PLAIN_PYPROJECT,
        "apps/gadget/pyproject.toml": _PY_PLAIN_PYPROJECT,
        "tests/widget/1_widget.md": _linked("1_widget_test.py"),
        "tests/gadget/1_widget_test.py": PY_TEST,
    }
    assert run_check_with_files(PY_CHECK_ID, files).findings == [
        fail("tests/gadget: story test(s) with no matching ### header: 1.1.1, 1.1.2"),
        fail("tests/widget: story-doc ### header(s) with no matching test: 1.1.1, 1.1.2"),
    ]


def test_15_8_3_rejects_duplicate_file_ids_across_languages(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {
        "tests/api/2-widget.test.ts": 'test("2.2 shows a widget", () => {});',
        "tests/admin/2_dashboard_test.py": "def test_2_1_shows_the_dashboard(): pass\n",
        "tests/api/conftest.py": "",
        "tests/admin/conftest.py": "",
    }
    assert run_check_with_files("unique_test_ids", files).findings == [
        fail("duplicate test file ID 2: tests/admin/2_dashboard_test.py, tests/api/2-widget.test.ts")
    ]


def test_15_8_4_allows_bare_and_prefixed_ids_in_the_same_repo(run_check_with_files: RunCheckWithFiles) -> None:
    files = {
        "tests/api/a2-widget.test.ts": 'test("a2.2 shows a widget", () => {});',
        "tests/admin/2_dashboard_test.py": "def test_2_2_shows_the_dashboard(): pass\n",
    }
    assert not run_check_with_files("unique_test_ids", files).problems


def test_15_8_5_rejects_case_ids_that_are_duplicate_or_belong_to_another_file(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {
        "tests/api/a2-widget.test.ts": 'test("a2.2 shows a widget", () => {}); test("a2.2 duplicate", () => {});',
        "tests/admin/2_dashboard_test.py": "def test_a2_2_shows_the_dashboard(): pass\n",
        "tests/3-empty.test.ts": "export {};\n",
    }
    assert run_check_with_files("unique_test_ids", files).findings == [
        fail("tests/3-empty.test.ts: no test cases found for ID 3"),
        fail("tests/admin/2_dashboard_test.py:1: test case must start with 2. followed by a number"),
        fail("tests/api/a2-widget.test.ts:1: duplicate test case ID a2.2"),
    ]


def test_15_8_6_checks_pytest_cases_and_ignores_helpers(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {
        "tests/2_dashboard_test.py": """\
from unittest import TestCase as Suite

def test_2_1_shows_dashboard():
    def test_helper(): pass

class Dashboard:
    def test_helper(self): pass

class TestDashboard:
    def test_2_2_loads_widgets(self): pass

class DashboardChecks(Suite):
    def test_unnumbered(self): pass
""",
    }
    assert run_check_with_files("unique_test_ids", files).findings == [
        fail("tests/2_dashboard_test.py:13: test case must start with 2. followed by a number"),
    ]


def test_15_8_7_checks_aliased_and_extended_vitest_cases(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {
        "tests/2-dashboard.test.ts": """\
import { test as scenario } from 'vitest';
import * as vitest from 'vitest';
const dashboard = scenario.extend<{ count: number }>({ count: 3 });
scenario('unnumbered', () => {});
dashboard('2.1 shows the dashboard', () => {});
dashboard.skip('2.1 duplicate', () => {});
vitest.test.skip('2.1 duplicate namespace', () => {});
""",
    }
    assert run_check_with_files("unique_test_ids", files).findings == [
        fail("tests/2-dashboard.test.ts:4: test case must start with 2. followed by a number"),
        fail("tests/2-dashboard.test.ts:6: duplicate test case ID 2.1"),
        fail("tests/2-dashboard.test.ts:7: duplicate test case ID 2.1"),
    ]


def test_15_8_8_ignores_shadowed_vitest_bindings(run_check_with_files: RunCheckWithFiles, fail: MakeFinding) -> None:
    files = {
        "tests/2-dashboard.test.ts": """\
import { describe, it, test, vi } from 'vitest';
const run = (it: () => void) => it();
describe('dashboard', () => {
  const it = vi.fn();
  it();
  test('2.1 shows dashboard', () => { const it = vi.fn(); it(); });
});
it('2.1 duplicate', () => {});
""",
    }
    assert run_check_with_files("unique_test_ids", files).findings == [
        fail("tests/2-dashboard.test.ts:8: duplicate test case ID 2.1"),
    ]


def test_15_8_9_checks_numeric_parameterized_case_ids(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {
        "tests/a2-dashboard.test.ts": """\
test.each([8, 9])('a2.%i with input %i', () => {});
test.for(['one', 'two'])('a2.4.%# with row %s', () => {});
test.for(['one', 'two'])('a2.5.%$ with row %s', () => {});
test('a2.9 duplicate', () => {});
test('a2.4.0 duplicate', () => {});
test('a2.5.2 duplicate', () => {});
""",
    }
    assert run_check_with_files("unique_test_ids", files).findings == [
        fail("tests/a2-dashboard.test.ts:4: duplicate test case ID a2.9"),
        fail("tests/a2-dashboard.test.ts:5: duplicate test case ID a2.4.0"),
        fail("tests/a2-dashboard.test.ts:6: duplicate test case ID a2.5.2"),
    ]
