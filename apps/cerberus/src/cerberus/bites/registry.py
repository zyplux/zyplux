from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cerberus.bites import (
    catalog_pinned_deps_bite,
    ci_cerberus_step_bite,
    ci_check_sequence_bite,
    ci_workflow_gate_bite,
    cli_py_test_seam_bite,
    cli_ts_test_seam_bite,
    codeowners_coverage_bite,
    fallow_analyzer_bite,
    jscpd_dupes_threshold_bite,
    justfile_baseline_bite,
    knip_standalone_config_bite,
    lib_py_test_seam_bite,
    lib_ts_test_seam_bite,
    line_length_120_bite,
    pyrefly_strict_bite,
    pytest_coverage_floor_bite,
    release_surface_version_bump_bite,
    ruff_select_all_bite,
    rumdl_canonical_config_bite,
    story_tests_lockstep_py_bite,
    story_tests_lockstep_ts_bite,
    tsc_project_references_bite,
    vitest_coverage_floor_bite,
    vitest_only_runner_bite,
    workflow_toolchain_only_bite,
    zyplux_deps_latest_bite,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo, Scope


@dataclass(frozen=True)
class Check:
    id: str
    summary: str
    scope: Scope
    run: Callable[[Repo, Context], CheckResult]


ALL: tuple[Check, ...] = tuple(
    Check(module.ID, module.SUMMARY, module.SCOPE, module.run)
    for module in (
        justfile_baseline_bite,
        ci_workflow_gate_bite,
        ci_check_sequence_bite,
        ci_cerberus_step_bite,
        workflow_toolchain_only_bite,
        pyrefly_strict_bite,
        ruff_select_all_bite,
        line_length_120_bite,
        rumdl_canonical_config_bite,
        knip_standalone_config_bite,
        vitest_only_runner_bite,
        tsc_project_references_bite,
        catalog_pinned_deps_bite,
        story_tests_lockstep_py_bite,
        story_tests_lockstep_ts_bite,
        cli_ts_test_seam_bite,
        lib_ts_test_seam_bite,
        cli_py_test_seam_bite,
        lib_py_test_seam_bite,
        release_surface_version_bump_bite,
        codeowners_coverage_bite,
        pytest_coverage_floor_bite,
        vitest_coverage_floor_bite,
        jscpd_dupes_threshold_bite,
        fallow_analyzer_bite,
        zyplux_deps_latest_bite,
    )
)

BY_ID: dict[str, Check] = {check.id: check for check in ALL}
