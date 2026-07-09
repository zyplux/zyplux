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
    fallow_bite,
    fixture_roles_ts_bite,
    jscpd_bite,
    justfile_bite,
    knip_bite,
    lib_py_test_seam_bite,
    lib_ts_test_seam_bite,
    line_length_bite,
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
        story_tests_lockstep_py_bite,
        story_tests_lockstep_ts_bite,
        cli_ts_test_seam_bite,
        lib_ts_test_seam_bite,
        fixture_roles_ts_bite,
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
