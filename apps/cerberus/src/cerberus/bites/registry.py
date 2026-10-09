from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cerberus.bites import (
    catalog_pinned_deps_bite,
    ci_cerberus_step_bite,
    ci_check_sequence_bite,
    ci_workflow_gate_bite,
    cli_py_test_seam_bite,
    codeowners_coverage_bite,
    consistent_package_export_entries_bite,
    consistent_workspace_project_references_bite,
    explicit_module_side_effects_bite,
    fallow_bite,
    jscpd_bite,
    justfile_bite,
    knip_bite,
    lib_py_test_seam_bite,
    line_length_bite,
    no_worker_filesystem_imports_bite,
    pnpm_release_age_bite,
    pyrefly_bite,
    pytest_bite,
    release_surface_version_bump_bite,
    ruff_bite,
    rumdl_bite,
    story_tests_lockstep_py_bite,
    story_tests_lockstep_ts_bite,
    tool_pins_latest_bite,
    tsc_bite,
    vitest_bite,
    vitest_coverage_bite,
    workflow_toolchain_only_bite,
    zyplux_deps_latest_bite,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo, Scope
    from cerberus.stacks import Language


@dataclass(frozen=True)
class Check:
    id: str
    summary: str
    scope: Scope
    run: Callable[[Repo, Context], CheckResult]
    languages: tuple[Language, ...] = ()


PYTHON_CHECKS = {
    "story_tests_lockstep_py",
    "cli_py_test_seam",
    "lib_py_test_seam",
}
TYPESCRIPT_CHECKS = {
    "vitest",
    "tsc",
    "consistent_package_export_entries",
    "explicit_module_side_effects",
    "consistent_workspace_project_references",
    "no_worker_filesystem_imports",
    "vitest_coverage",
    "story_tests_lockstep_ts",
    "fallow",
}


def _list_languages(check_id: str) -> tuple[Language, ...]:
    if check_id in PYTHON_CHECKS:
        return ("python",)
    if check_id in TYPESCRIPT_CHECKS:
        return ("typescript",)
    if check_id == "jscpd":
        return ("python", "typescript")
    return ()


ALL: tuple[Check, ...] = tuple(
    Check(module.ID, module.SUMMARY, module.SCOPE, module.run, _list_languages(module.ID))
    for module in (
        justfile_bite,
        ci_workflow_gate_bite,
        ci_check_sequence_bite,
        ci_cerberus_step_bite,
        workflow_toolchain_only_bite,
        pyrefly_bite,
        ruff_bite,
        line_length_bite,
        rumdl_bite,
        knip_bite,
        vitest_bite,
        tsc_bite,
        catalog_pinned_deps_bite,
        consistent_package_export_entries_bite,
        explicit_module_side_effects_bite,
        consistent_workspace_project_references_bite,
        no_worker_filesystem_imports_bite,
        vitest_coverage_bite,
        pnpm_release_age_bite,
        story_tests_lockstep_py_bite,
        story_tests_lockstep_ts_bite,
        cli_py_test_seam_bite,
        lib_py_test_seam_bite,
        release_surface_version_bump_bite,
        codeowners_coverage_bite,
        pytest_bite,
        jscpd_bite,
        fallow_bite,
        zyplux_deps_latest_bite,
        tool_pins_latest_bite,
    )
)

BY_ID: dict[str, Check] = {check.id: check for check in ALL}

RETIRED = {
    "package_exports": "consistent_package_export_entries",
    "package_side_effects": "explicit_module_side_effects",
    "project_references": "consistent_workspace_project_references",
    "worker_runtime": "no_worker_filesystem_imports",
    "contract_keepers": "repository-local tests",
    "dependency_direction": "repository-local tests",
    "cli_ts_test_seam": (
        "consistent_package_export_entries and ESLint "
        "test-seam-only-imports/use-package-type-exports/no-type-only-dependencies"
    ),
    "lib_ts_test_seam": (
        "consistent_package_export_entries and ESLint "
        "test-seam-only-imports/use-package-type-exports/no-type-only-dependencies"
    ),
    "fixture_roles_ts": "ESLint test-seam-only-imports/use-package-type-exports/no-type-only-dependencies",
}
