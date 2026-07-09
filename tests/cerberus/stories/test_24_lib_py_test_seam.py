from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult
    from seam_fixtures import MakeFinding, RunCheckWithFiles

type RunLibPyTests = Callable[[dict[str, str]], CheckResult]

CHECK_ID = "lib_py_test_seam"

_ROOT_WS = '[tool.uv.workspace]\nmembers = ["packages/lib"]\n'
_ROOT_WS_CLI_ONLY = '[tool.uv.workspace]\nmembers = ["apps/cli"]\n'

_LIB_MANIFEST = '[project]\nname = "demo-lib"\n\n[tool.uv.build-backend]\nmodule-name = "demolib"\n'
_LIB_MANIFEST_EMPTY_SCRIPTS = (
    '[project]\nname = "demo-lib"\n\n[project.scripts]\n\n[tool.uv.build-backend]\nmodule-name = "demolib"\n'
)
_CLI_MANIFEST = (
    '[project]\nname = "demo-cli"\n\n[project.scripts]\ncli = "demo.cli:app"\n\n'
    '[tool.uv.build-backend]\nmodule-name = "demo"\n'
)

_LIB_INIT = (
    '"""Demo library."""\n\nfrom __future__ import annotations\n\n\ndef helper() -> str:\n    return "hi"\n\n\n'
    "def _internal() -> None:\n    return None\n"
)

_STORY_FILE = "packages/lib/tests/stories/test_1_first.py"
_BASE_FILES = {
    "pyproject.toml": _ROOT_WS,
    "packages/lib/pyproject.toml": _LIB_MANIFEST,
    "packages/lib/src/demolib/__init__.py": _LIB_INIT,
}

_OK_MESSAGE = "every library's story tests import only their root module"


def _with_story(content: str) -> dict[str, str]:
    return {**_BASE_FILES, _STORY_FILE: content}


@pytest.fixture
def run_lib_py_tests(run_check_with_files: RunCheckWithFiles) -> RunLibPyTests:
    return partial(run_check_with_files, CHECK_ID)


def test_24_1_1_skips_repos_with_no_python_packages(run_lib_py_tests: RunLibPyTests, skip: MakeFinding) -> None:
    result = run_lib_py_tests({})
    assert result.findings == [skip("no Python packages")]


def test_24_1_2_skips_workspaces_with_no_library(run_lib_py_tests: RunLibPyTests, skip: MakeFinding) -> None:
    result = run_lib_py_tests({
        "pyproject.toml": _ROOT_WS_CLI_ONLY,
        "apps/cli/pyproject.toml": _CLI_MANIFEST,
    })
    assert result.findings == [skip("no libraries")]


def test_24_1_3_treats_a_package_with_an_empty_project_scripts_table_as_a_library(
    run_lib_py_tests: RunLibPyTests, ok: MakeFinding
) -> None:
    result = run_lib_py_tests({
        "pyproject.toml": _ROOT_WS,
        "packages/lib/pyproject.toml": _LIB_MANIFEST_EMPTY_SCRIPTS,
        "packages/lib/src/demolib/__init__.py": _LIB_INIT,
    })
    assert result.findings == [ok(_OK_MESSAGE)]


def test_24_2_1_passes_a_story_test_importing_only_public_names_of_the_root_module(
    run_lib_py_tests: RunLibPyTests, ok: MakeFinding
) -> None:
    result = run_lib_py_tests(_with_story("from demolib import helper\n"))
    assert result.findings == [ok(_OK_MESSAGE)]


def test_24_2_2_fails_a_story_test_with_a_relative_import(run_lib_py_tests: RunLibPyTests, fail: MakeFinding) -> None:
    result = run_lib_py_tests(_with_story("from .util import helper\n"))
    assert result.findings == [fail(f"{_STORY_FILE}: story test imports outside the seam — '.util'")]


def test_24_2_3_fails_a_story_test_importing_a_deep_submodule(
    run_lib_py_tests: RunLibPyTests, fail: MakeFinding
) -> None:
    result = run_lib_py_tests(_with_story("from demolib.internal import Thing\n"))
    assert result.findings == [fail(f"{_STORY_FILE}: story test imports outside the seam — 'demolib.internal'")]


def test_24_2_4_fails_a_story_test_importing_a_non_public_name_from_the_root_module(
    run_lib_py_tests: RunLibPyTests, fail: MakeFinding
) -> None:
    result = run_lib_py_tests(_with_story("from demolib import _internal\n"))
    assert result.findings == [
        fail(f"{_STORY_FILE}: story test imports non-public name '_internal' from seam module 'demolib'")
    ]


def test_24_2_5_allows_a_story_test_to_import_a_third_party_module_directly(
    run_lib_py_tests: RunLibPyTests, ok: MakeFinding
) -> None:
    result = run_lib_py_tests(_with_story("import pytest\n"))
    assert result.findings == [ok(_OK_MESSAGE)]


def test_24_2_6_passes_a_disallowed_import_guarded_under_type_checking(
    run_lib_py_tests: RunLibPyTests, ok: MakeFinding
) -> None:
    guarded = (
        "from __future__ import annotations\n\nfrom typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n    from demolib.internal import Thing\n"
    )
    result = run_lib_py_tests(_with_story(guarded))
    assert result.findings == [ok(_OK_MESSAGE)]


def test_24_2_7_passes_a_disallowed_import_guarded_under_a_dotted_type_checking_attribute(
    run_lib_py_tests: RunLibPyTests, ok: MakeFinding
) -> None:
    guarded = (
        "from __future__ import annotations\n\nimport typing\n\n"
        "if typing.TYPE_CHECKING:\n    from demolib.internal import Thing\n"
    )
    result = run_lib_py_tests(_with_story(guarded))
    assert result.findings == [ok(_OK_MESSAGE)]


def test_24_2_8_fails_a_story_test_with_a_bare_import_of_a_deep_submodule(
    run_lib_py_tests: RunLibPyTests, fail: MakeFinding
) -> None:
    result = run_lib_py_tests(_with_story("import demolib.internal\n"))
    assert result.findings == [fail(f"{_STORY_FILE}: story test imports outside the seam — 'demolib.internal'")]


def test_24_2_9_passes_a_story_test_importing_an_annotated_top_level_constant_from_the_root_module(
    run_lib_py_tests: RunLibPyTests, ok: MakeFinding
) -> None:
    lib_init = '"""Demo library."""\n\nfrom __future__ import annotations\n\n\nTIMEOUT: int = 30\n'
    files = {
        **_BASE_FILES,
        "packages/lib/src/demolib/__init__.py": lib_init,
        _STORY_FILE: "from demolib import TIMEOUT\n",
    }
    result = run_lib_py_tests(files)
    assert result.findings == [ok(_OK_MESSAGE)]


def test_24_3_1_skips_cleanly_when_a_package_has_no_story_test_files_yet(
    run_lib_py_tests: RunLibPyTests, ok: MakeFinding
) -> None:
    result = run_lib_py_tests(_BASE_FILES)
    assert result.findings == [ok(_OK_MESSAGE)]
