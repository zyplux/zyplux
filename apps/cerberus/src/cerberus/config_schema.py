from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, create_model

_SCHEMA_CONFIG = ConfigDict(strict=True, extra="forbid")
BiteSettings = create_model("BiteSettings", __config__=_SCHEMA_CONFIG, off=(bool, None))
RecipeSettings = create_model("RecipeSettings", __config__=_SCHEMA_CONFIG, recipe=str, alias=(str, None))
SourceRoots = create_model("SourceRoots", __config__=_SCHEMA_CONFIG, roots=(list[str], None))
CoverageSettings = create_model("CoverageSettings", __base__=BiteSettings, min_coverage=(int, None))
CONFIG_SCHEMA = create_model(
    "CerberusSettings",
    __config__=_SCHEMA_CONFIG,
    justfile=(
        create_model(
            "JustfileSettings",
            __base__=BiteSettings,
            default_recipe_marker=(str, None),
            required=(list[RecipeSettings], None),
            recommended=(list[RecipeSettings], None),
            check_pipeline=(list[str], None),
            wrapped_tools=(list[str], None),
        ),
        None,
    ),
    ci_workflow_gate=(BiteSettings, None),
    ci_check_sequence=(
        create_model(
            "SequenceSettings",
            __base__=BiteSettings,
            required=(
                create_model(
                    "PipelineSettings", __config__=_SCHEMA_CONFIG, ts=(list[str], None), python=(list[str], None)
                ),
                None,
            ),
        ),
        None,
    ),
    ci_cerberus_step=(BiteSettings, None),
    workflow_toolchain_only=(
        create_model("ToolchainSettings", __base__=BiteSettings, allowed_setup_actions=(list[str], None)),
        None,
    ),
    source_oracle=(
        create_model(
            "OracleSettings",
            __base__=BiteSettings,
            default_type=(Literal["prod", "infra", "demo", "test", "docs"], None),
            test_files=(list[str], None),
            test_exempt_files=(list[str], None),
            types=(
                create_model(
                    "SourceTypes",
                    __config__=_SCHEMA_CONFIG,
                    prod=(SourceRoots, None),
                    infra=(SourceRoots, None),
                    demo=(SourceRoots, None),
                    test=(SourceRoots, None),
                    docs=(SourceRoots, None),
                ),
                None,
            ),
        ),
        None,
    ),
    pyrefly=(create_model("PyreflySettings", __base__=BiteSettings, error_kinds=(list[str], None)), None),
    ruff=(
        create_model(
            "RuffSettings",
            __base__=BiteSettings,
            sanctioned_ignore=(list[str], None),
            sanctioned_test_ignore=(list[str], None),
        ),
        None,
    ),
    line_length=(create_model("LineSettings", __base__=BiteSettings, width=(int, None)), None),
    rumdl=(create_model("RumdlSettings", __base__=BiteSettings, canonical=(str, None)), None),
    knip=(
        create_model(
            "KnipSettings",
            __base__=BiteSettings,
            prod_allowed_exclude=(list[str], None),
            allowed_customizations=(dict[str, list[str]], None),
        ),
        None,
    ),
    vitest=(BiteSettings, None),
    vitest_coverage=(CoverageSettings, None),
    tsc=(BiteSettings, None),
    catalog_pinned_deps=(BiteSettings, None),
    consistent_package_export_entries=(BiteSettings, None),
    explicit_module_side_effects=(BiteSettings, None),
    consistent_workspace_project_references=(BiteSettings, None),
    no_worker_filesystem_imports=(BiteSettings, None),
    pnpm_release_age=(BiteSettings, None),
    story_tests_lockstep_py=(BiteSettings, None),
    story_tests_lockstep_ts=(BiteSettings, None),
    cli_py_test_seam=(BiteSettings, None),
    lib_py_test_seam=(BiteSettings, None),
    release_readiness=(BiteSettings, None),
    release_surface_version_bump=(BiteSettings, None),
    codeowners_coverage=(BiteSettings, None),
    pytest=(CoverageSettings, None),
    jscpd=(
        create_model(
            "JscpdSettings",
            __base__=BiteSettings,
            threshold=(float, None),
            pattern=(str, None),
            ignore=(list[str], None),
        ),
        None,
    ),
    fallow=(
        create_model(
            "FallowSettings",
            __base__=BiteSettings,
            entry_points=(list[str], None),
            coverage_report=(str, None),
            rules=(dict[str, Literal["off", "warn", "error"]], None),
        ),
        None,
    ),
    zyplux_deps_latest=(BiteSettings, None),
    tool_pins_latest=(BiteSettings, None),
)
