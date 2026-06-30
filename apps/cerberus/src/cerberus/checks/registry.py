from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cerberus.checks import (
    catalog_discipline_check,
    cerberus_step_check,
    ci_sequence_check,
    ci_workflow_check,
    codeowners_check,
    justfile_check,
    line_length_check,
    pyrefly_config_check,
    release_bumps_check,
    ruff_config_check,
    rumdl_config_check,
    ts_project_references_check,
    vitest_runner_check,
    workflow_tooling_check,
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
        justfile_check,
        ci_workflow_check,
        ci_sequence_check,
        cerberus_step_check,
        workflow_tooling_check,
        pyrefly_config_check,
        ruff_config_check,
        line_length_check,
        rumdl_config_check,
        vitest_runner_check,
        ts_project_references_check,
        catalog_discipline_check,
        release_bumps_check,
        codeowners_check,
    )
)

BY_ID: dict[str, Check] = {check.id: check for check in ALL}
