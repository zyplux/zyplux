from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cerberus.checks import (
    catalog_discipline_check,
    cerberus_step_check,
    ci_sequence_check,
    ci_workflow_check,
    codeowners_check,
    justfile_check,
    release_bumps_check,
    ruleset_check,
    rumdl_config_check,
    secrets_check,
    ts_project_references_check,
    vitest_runner_check,
    workflow_tooling_check,
)
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
        rumdl_config_check,
        vitest_runner_check,
        ts_project_references_check,
        catalog_discipline_check,
        release_bumps_check,
        ruleset_check,
        secrets_check,
        codeowners_check,
    )
)

BY_ID: dict[str, Check] = {check.id: check for check in ALL}

CONTENT: tuple[Check, ...] = tuple(c for c in ALL if c.scope is Scope.CONTENT)
