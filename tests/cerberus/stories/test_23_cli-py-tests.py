from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Finding, Status

type RunCheckWithFiles = Callable[[str, dict[str, str]], CheckResult]
type RunCliPyTests = Callable[[dict[str, str]], CheckResult]

CHECK_ID = "cli-py-tests"

_ROOT_WS = '[tool.uv.workspace]\nmembers = ["apps/cli"]\n'
_ROOT_WS_LIB_ONLY = '[tool.uv.workspace]\nmembers = ["packages/lib"]\n'

_CLI_MANIFEST = (
    '[project]\nname = "demo-cli"\n\n'
    '[project.scripts]\ncli = "demo.cli:app"\n\n'
    '[tool.uv.build-backend]\nmodule-name = "demo"\n'
)
_CLI_MANIFEST_NO_BUILD_BACKEND = '[project]\nname = "demo-cli"\n\n[project.scripts]\ncli = "demo.cli:app"\n'
_LIB_MANIFEST = '[project]\nname = "demo-lib"\n\n[tool.uv.build-backend]\nmodule-name = "demolib"\n'

_ROOT_INIT = (
    '"""Demo package."""\n\n'
    "from __future__ import annotations\n\n\n"
    'def greet() -> str:\n    return "hi"\n\n\n'
    "def _internal() -> None:\n    return None\n"
)
_CLI_MODULE = "from __future__ import annotations\n\nimport typer\n\napp = typer.Typer()\n"

_STORY_FILE = "apps/cli/tests/stories/test_1_first.py"
_BASE_FILES = {
    "pyproject.toml": _ROOT_WS,
    "apps/cli/pyproject.toml": _CLI_MANIFEST,
    "apps/cli/src/demo/__init__.py": _ROOT_INIT,
    "apps/cli/src/demo/cli.py": _CLI_MODULE,
}

_OK_MESSAGE = "every cli app's story tests import only the root module or their cli entry module"


def _with_story(content: str) -> dict[str, str]:
    return {**_BASE_FILES, _STORY_FILE: content}


@pytest.fixture
def run_cli_py_tests(run_check_with_files: RunCheckWithFiles) -> RunCliPyTests:
    def _run(files: dict[str, str]) -> CheckResult:
        return run_check_with_files(CHECK_ID, files)

    return _run


def test_23_1_1_skips_repos_with_no_python_packages(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests({})
    assert result.findings == [finding(status.SKIP, "no Python packages")]


def test_23_1_2_skips_workspaces_with_no_cli_app(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests({
        "pyproject.toml": _ROOT_WS_LIB_ONLY,
        "packages/lib/pyproject.toml": _LIB_MANIFEST,
        "packages/lib/src/demolib/__init__.py": "",
    })
    assert result.findings == [finding(status.SKIP, "no cli apps")]


def test_23_2_1_resolves_the_root_module_from_build_backend_module_name(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests({
        "pyproject.toml": _ROOT_WS,
        "apps/cli/pyproject.toml": _CLI_MANIFEST,
        _STORY_FILE: "from demo.internal import Thing\n",
    })
    assert result.findings == [
        finding(status.FAIL, f"{_STORY_FILE}: story test imports outside the seam — 'demo.internal'")
    ]


def test_23_2_2_resolves_the_root_module_from_the_shallowest_init_file_when_module_name_is_absent(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests({
        "pyproject.toml": _ROOT_WS,
        "apps/cli/pyproject.toml": _CLI_MANIFEST_NO_BUILD_BACKEND,
        "apps/cli/src/demo/__init__.py": "",
        "apps/cli/src/demo/sub/__init__.py": "",
        _STORY_FILE: "from demo.other import Thing\n",
    })
    assert result.findings == [
        finding(status.FAIL, f"{_STORY_FILE}: story test imports outside the seam — 'demo.other'")
    ]


def test_23_2_3_errors_when_the_root_module_cannot_be_resolved(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests({
        "pyproject.toml": _ROOT_WS,
        "apps/cli/pyproject.toml": _CLI_MANIFEST_NO_BUILD_BACKEND,
    })
    assert result.findings == [finding(status.ERROR, "apps/cli: could not determine the package's import root")]


def test_23_3_1_passes_a_story_test_importing_only_public_names_of_the_root_module(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests(_with_story("from demo import greet\n"))
    assert result.findings == [finding(status.PASS, _OK_MESSAGE)]


def test_23_3_2_passes_a_story_test_importing_public_names_of_the_cli_entry_module(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests(_with_story("from demo.cli import app\n"))
    assert result.findings == [finding(status.PASS, _OK_MESSAGE)]


def test_23_3_3_fails_a_story_test_with_a_relative_import(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests(_with_story("from .util import helper\n"))
    assert result.findings == [finding(status.FAIL, f"{_STORY_FILE}: story test imports outside the seam — '.util'")]


def test_23_3_4_fails_a_story_test_importing_a_deep_submodule(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests(_with_story("from demo.internal import Thing\n"))
    assert result.findings == [
        finding(status.FAIL, f"{_STORY_FILE}: story test imports outside the seam — 'demo.internal'")
    ]


def test_23_3_5_fails_a_story_test_importing_a_non_public_name_from_the_root_module(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests(_with_story("from demo import _internal\n"))
    assert result.findings == [
        finding(status.FAIL, f"{_STORY_FILE}: story test imports non-public name '_internal' from seam module 'demo'")
    ]


def test_23_3_6_allows_a_story_test_to_import_a_third_party_module_directly(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests(_with_story("import pytest\n"))
    assert result.findings == [finding(status.PASS, _OK_MESSAGE)]


def test_23_3_7_passes_a_disallowed_import_guarded_under_type_checking(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    guarded = (
        "from __future__ import annotations\n\n"
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    from demo.internal import Thing\n"
    )
    result = run_cli_py_tests(_with_story(guarded))
    assert result.findings == [finding(status.PASS, _OK_MESSAGE)]


def test_23_3_8_does_not_exempt_an_import_in_the_else_branch_of_a_type_checking_guard(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    guarded_else = (
        "from __future__ import annotations\n\n"
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    pass\n"
        "else:\n"
        "    from demo.internal import Thing\n"
    )
    result = run_cli_py_tests(_with_story(guarded_else))
    assert result.findings == [
        finding(status.FAIL, f"{_STORY_FILE}: story test imports outside the seam — 'demo.internal'")
    ]


def test_23_3_9_restricts_the_public_surface_to_a_declared_all_list(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    root_init = (
        '"""Demo package."""\n\n'
        "from __future__ import annotations\n\n\n"
        '__all__ = ["greet"]\n\n\n'
        'def greet() -> str:\n    return "hi"\n\n\n'
        'def other() -> str:\n    return "meh"\n'
    )
    files = {**_BASE_FILES, "apps/cli/src/demo/__init__.py": root_init, _STORY_FILE: "from demo import other\n"}
    result = run_cli_py_tests(files)
    assert result.findings == [
        finding(status.FAIL, f"{_STORY_FILE}: story test imports non-public name 'other' from seam module 'demo'")
    ]


def test_23_4_1_skips_cleanly_when_a_package_has_no_story_test_files_yet(
    run_cli_py_tests: RunCliPyTests, finding: type[Finding], status: type[Status]
) -> None:
    result = run_cli_py_tests(_BASE_FILES)
    assert result.findings == [finding(status.PASS, _OK_MESSAGE)]
