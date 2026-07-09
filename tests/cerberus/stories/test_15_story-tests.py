from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from seam_fixtures import MakeFinding, RunCheckOnDisk, RunCheckWithFiles


PY_CHECK_ID = "story-tests-py"
TS_CHECK_ID = "story-tests-ts"

DOC = (
    "# 1. Configuring a widget\n\n## 1.1 Widget setup\n\n"
    "### 1.1.1 shows the widget name\n\n### 1.1.2 accepts a custom color\n"
)
DOC_PATH = "tests/stories/1_widget.md"

PY_TEST_PATH = "tests/stories/test_1_widget.py"
PY_TEST = "def test_1_1_1_shows_the_widget_name():\n    pass\n\n\ndef test_1_1_2_accepts_a_custom_color():\n    pass\n"

TS_DOC_PATH = "tests/stories/1-widget.md"
TS_TEST_PATH = "tests/stories/1-widget.test.ts"
TS_TEST = "test('1.1.1 shows the widget name', () => {});\ntest('1.1.2 accepts a custom color', () => {});\n"

_PY_PLAIN_PYPROJECT = '[project]\nname = "widget"\n'
_PY_SCRIPTS_PYPROJECT = '[project]\nname = "widget"\n\n[project.scripts]\nwidget = "widget.cli:main"\n'
_PY_UV_WORKSPACE_APPS = '[tool.uv.workspace]\nmembers = ["apps/*"]\n'
_PY_UV_WORKSPACE_SERVICES = '[tool.uv.workspace]\nmembers = ["services/*"]\n'

_TS_PLAIN_PKG = '{"name": "widget"}'
_TS_BIN_PKG = '{"name": "widget", "bin": {"widget": "./src/index.ts"}}'
_TS_BUN_WORKSPACE_APPS = '{"workspaces": ["apps/*"]}'
_TS_BUN_WORKSPACE_WITH_TESTS_MEMBER = '{"workspaces": ["apps/*", "tests"]}'

OK_MESSAGE = "every story criterion has a matching, title-matched test"
NO_MATCHING_TEST_HEADER_MESSAGE = "tests/stories: story-doc ### header(s) with no matching test: 1.1.2"
PY_STALE_LINK_MESSAGE = "tests/stories/1_widget.md: story header links are stale; run with --fix"
TS_STALE_LINK_MESSAGE = "tests/stories/1-widget.md: story header links are stale; run with --fix"
TITLE_DRIFT_MESSAGE = (
    "tests/stories: header/test title drift for 1.1.1 — header='shows the widget name' test='shows a different name'"
)


def _needs_story_tests_message(package: str) -> str:
    return f"{package}: exposes a public interface but has no tests/**/stories/*.md user-story tests"


NEEDS_STORY_TESTS_MESSAGE = _needs_story_tests_message(".")


def _linked(target: str) -> str:
    return DOC.replace("# 1. Configuring a widget\n", f"# 1. [Configuring a widget]({target})\n")


def test_15_1_1_skips_a_repo_with_no_python_packages_at_all(
    run_check_with_files: RunCheckWithFiles, skip: MakeFinding
) -> None:
    result = run_check_with_files(PY_CHECK_ID, {"README.md": "# demo\n"})
    assert result.findings == [skip("no Python packages")]


def test_15_1_2_skips_a_repo_with_no_typescript_packages_at_all(
    run_check_with_files: RunCheckWithFiles, skip: MakeFinding
) -> None:
    result = run_check_with_files(TS_CHECK_ID, {"README.md": "# demo\n"})
    assert result.findings == [skip("no TypeScript packages")]


def test_15_1_3_ignores_a_directory_outside_the_workspace_glob(
    run_check_with_files: RunCheckWithFiles, skip: MakeFinding
) -> None:
    files = {"pyproject.toml": _PY_UV_WORKSPACE_APPS, "libs/other/pyproject.toml": _PY_SCRIPTS_PYPROJECT}
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [skip("no Python packages")]


def test_15_1_4_excludes_the_top_level_tests_directory_from_being_treated_as_a_package(
    run_check_with_files: RunCheckWithFiles, skip: MakeFinding
) -> None:
    files = {
        "package.json": _TS_BUN_WORKSPACE_WITH_TESTS_MEMBER,
        "tests/package.json": '{"name": "test-harness"}',
        "tests/some.test.ts": "test('does nothing special', () => {});\n",
    }
    result = run_check_with_files(TS_CHECK_ID, files)
    assert result.findings == [skip("no TypeScript packages")]


def test_15_1_5_treats_a_nested_tests_directory_as_excluded_but_still_checks_its_sibling_package(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {
        "package.json": '{"workspaces": ["apps/*", "tests/*"]}',
        "apps/cz/package.json": _TS_BIN_PKG,
        "tests/cz/package.json": '{"name": "test-harness-cz"}',
    }
    result = run_check_with_files(TS_CHECK_ID, files)
    assert result.findings == [fail(_needs_story_tests_message("apps/cz"))]


def test_15_1_6_recognizes_a_workspaces_object_with_a_packages_list(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {
        "package.json": '{"workspaces": {"packages": ["apps/*"]}}',
        "apps/widget/package.json": _TS_BIN_PKG,
    }
    result = run_check_with_files(TS_CHECK_ID, files)
    assert result.findings == [fail(_needs_story_tests_message("apps/widget"))]


def test_15_2_1_fails_a_python_package_that_exposes_a_cli_script_but_has_no_story_tests(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    result = run_check_with_files(PY_CHECK_ID, {"pyproject.toml": _PY_SCRIPTS_PYPROJECT})
    assert result.findings == [fail(NEEDS_STORY_TESTS_MESSAGE)]


def test_15_2_2_fails_a_typescript_package_that_exposes_a_bin_entry_but_has_no_story_tests(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    result = run_check_with_files(TS_CHECK_ID, {"package.json": _TS_BIN_PKG})
    assert result.findings == [fail(NEEDS_STORY_TESTS_MESSAGE)]


def test_15_2_3_skips_a_python_package_with_no_public_interface_and_no_tests(
    run_check_with_files: RunCheckWithFiles, skip: MakeFinding
) -> None:
    result = run_check_with_files(PY_CHECK_ID, {"pyproject.toml": _PY_PLAIN_PYPROJECT})
    assert result.findings == [skip("no Python package needs story-based tests")]


def test_15_2_4_skips_a_typescript_package_with_no_public_interface_and_no_tests(
    run_check_with_files: RunCheckWithFiles, skip: MakeFinding
) -> None:
    result = run_check_with_files(TS_CHECK_ID, {"package.json": _TS_PLAIN_PKG})
    assert result.findings == [skip("no TypeScript package needs story-based tests")]


def test_15_2_5_fails_a_python_package_that_already_has_plain_tests_but_no_story_docs(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {"pyproject.toml": _PY_PLAIN_PYPROJECT, "tests/test_widget.py": "def test_it():\n    pass\n"}
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [fail(NEEDS_STORY_TESTS_MESSAGE)]


def test_15_2_6_fails_a_typescript_package_that_already_has_plain_tests_but_no_story_docs(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    files = {"package.json": _TS_PLAIN_PKG, "tests/widget.test.ts": "test('does a thing', () => {});\n"}
    result = run_check_with_files(TS_CHECK_ID, files)
    assert result.findings == [fail(NEEDS_STORY_TESTS_MESSAGE)]


def test_15_3_1_passes_a_python_workspace_member_with_colocated_story_tests(
    run_check_with_files: RunCheckWithFiles, ok: MakeFinding
) -> None:
    files = {
        "pyproject.toml": _PY_UV_WORKSPACE_APPS,
        "apps/widget/pyproject.toml": _PY_SCRIPTS_PYPROJECT,
        "apps/widget/tests/stories/1_widget.md": _linked("test_1_widget.py"),
        "apps/widget/tests/stories/test_1_widget.py": PY_TEST,
    }
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [ok(OK_MESSAGE)]


def test_15_3_2_passes_a_typescript_workspace_member_with_colocated_story_tests(
    run_check_with_files: RunCheckWithFiles, ok: MakeFinding
) -> None:
    files = {
        "package.json": _TS_BUN_WORKSPACE_APPS,
        "apps/widget/package.json": _TS_BIN_PKG,
        "apps/widget/tests/stories/1-widget.md": _linked("1-widget.test.ts"),
        "apps/widget/tests/stories/1-widget.test.ts": TS_TEST,
    }
    result = run_check_with_files(TS_CHECK_ID, files)
    assert result.findings == [ok(OK_MESSAGE)]


@pytest.mark.parametrize(
    ("check_id", "files"),
    [
        (
            PY_CHECK_ID,
            {
                "pyproject.toml": _PY_UV_WORKSPACE_APPS,
                "apps/widget/pyproject.toml": _PY_SCRIPTS_PYPROJECT,
                "tests/widget/stories/1_widget.md": _linked("test_1_widget.py"),
                "tests/widget/stories/test_1_widget.py": PY_TEST,
            },
        ),
        (
            TS_CHECK_ID,
            {
                "package.json": _TS_BUN_WORKSPACE_APPS,
                "apps/widget/package.json": _TS_BIN_PKG,
                "tests/widget/stories/1-widget.md": _linked("1-widget.test.ts"),
                "tests/widget/stories/1-widget.test.ts": TS_TEST,
            },
        ),
    ],
    ids=["python", "typescript"],
)
def test_15_3_3_passes_a_workspace_member_whose_story_tests_are_torn_out_to_a_top_level_tests_directory(
    run_check_with_files: RunCheckWithFiles, check_id: str, files: dict[str, str], ok: MakeFinding
) -> None:
    result = run_check_with_files(check_id, files)
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
            PY_TEST_PATH: "def test_1_1_1_shows_the_widget_name():\n    pass\n",
        },
        PY_STALE_LINK_MESSAGE,
    ),
    StaleHeaderCase(
        TS_CHECK_ID,
        {
            "package.json": _TS_PLAIN_PKG,
            TS_DOC_PATH: DOC,
            TS_TEST_PATH: "test('1.1.1 shows the widget name', () => {});\n",
        },
        TS_STALE_LINK_MESSAGE,
    ),
]


@pytest.mark.parametrize("case", _NO_MATCHING_TEST_CASES, ids=["python", "typescript"])
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
    StaleHeaderCase(
        TS_CHECK_ID,
        {
            "package.json": _TS_PLAIN_PKG,
            TS_DOC_PATH: DOC,
            TS_TEST_PATH: TS_TEST.replace("shows the widget name", "shows a different name"),
        },
        TS_STALE_LINK_MESSAGE,
    ),
]


@pytest.mark.parametrize("case", _TITLE_DRIFT_CASES, ids=["python", "typescript"])
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
        DOC_PATH: _linked("test_1_widget.py").replace("shows the widget name", "shows the widget's fileName.txt"),
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
        "test_1_widget.py",
        PY_TEST,
        "test_1_widget.py",
        "1_widget.md",
        PY_CHECK_ID,
    ),
    StaleLinkCase(
        "package.json",
        _TS_PLAIN_PKG,
        "1-widget.test.ts",
        TS_TEST,
        "1-widget.test.ts",
        "1-widget.md",
        TS_CHECK_ID,
    ),
]


@pytest.mark.parametrize("case", _STALE_LINK_CASES, ids=["python", "typescript"])
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
        DOC_PATH: _linked("test_1_widget.py").replace(
            "### 1.1.1 shows the widget name",
            "### 1.1.1 [shows the widget name](test_1_widget.py)",
        ),
        PY_TEST_PATH: PY_TEST,
    }
    result = run_check_with_files(PY_CHECK_ID, files)
    assert result.findings == [fail(PY_STALE_LINK_MESSAGE)]


def test_15_6_1_recognizes_test_calls_written_with_chained_modifiers(
    run_check_with_files: RunCheckWithFiles, ok: MakeFinding
) -> None:
    test_content = (
        "it.concurrent('1.1.1 shows the widget name', async () => {});\n"
        "test.skip('1.1.2 accepts a custom color', () => {});\n"
    )
    files = {"package.json": _TS_PLAIN_PKG, TS_DOC_PATH: _linked("1-widget.test.ts"), TS_TEST_PATH: test_content}
    result = run_check_with_files(TS_CHECK_ID, files)
    assert result.findings == [ok(OK_MESSAGE)]


def test_15_6_2_recognizes_test_calls_written_with_a_parametrized_each_table(
    run_check_with_files: RunCheckWithFiles, ok: MakeFinding
) -> None:
    test_content = (
        "test.each([\n"
        "  ['red', () => paint('red', { intensity: 1 })],\n"
        "  ['blue', () => paint('blue', { intensity: 2 })],\n"
        "] as const)('1.1.1 shows the widget name', (_color, invoke) => {\n"
        "  invoke();\n"
        "});\n"
        "test('1.1.2 accepts a custom color', () => {});\n"
    )
    files = {"package.json": _TS_PLAIN_PKG, TS_DOC_PATH: _linked("1-widget.test.ts"), TS_TEST_PATH: test_content}
    result = run_check_with_files(TS_CHECK_ID, files)
    assert result.findings == [ok(OK_MESSAGE)]


def test_15_6_3_recognizes_a_title_that_contains_a_different_quote_character_than_its_delimiter(
    run_check_with_files: RunCheckWithFiles, fail: MakeFinding
) -> None:
    test_content = "it(\"1.1.1 shows the widget's name\", () => {});\ntest('1.1.2 accepts a custom color', () => {});\n"
    files = {"package.json": _TS_PLAIN_PKG, TS_DOC_PATH: _linked("1-widget.test.ts"), TS_TEST_PATH: test_content}
    result = run_check_with_files(TS_CHECK_ID, files)
    assert result.findings == [
        fail(
            "tests/stories: header/test title drift for 1.1.1 — "
            "header='shows the widget name' test=\"shows the widget's name\"",
        )
    ]


def test_15_7_1_scopes_each_check_to_only_its_own_language_packages_in_a_mixed_repo(
    run_check_with_files: RunCheckWithFiles, ok: MakeFinding, fail: MakeFinding
) -> None:
    files = {
        "package.json": _TS_BUN_WORKSPACE_APPS,
        "pyproject.toml": _PY_UV_WORKSPACE_SERVICES,
        "apps/widget/package.json": _TS_BIN_PKG,
        "apps/widget/tests/stories/1-widget.md": _linked("1-widget.test.ts"),
        "apps/widget/tests/stories/1-widget.test.ts": TS_TEST,
        "services/gizmo/pyproject.toml": _PY_SCRIPTS_PYPROJECT,
    }
    ts_result = run_check_with_files(TS_CHECK_ID, files)
    py_result = run_check_with_files(PY_CHECK_ID, files)
    assert ts_result.findings == [ok(OK_MESSAGE)]
    assert py_result.findings == [fail(_needs_story_tests_message("services/gizmo"))]
