from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult, Status
    from seam_fixtures import MakeFinding, RunCheckWithFiles

type RunKnipConfig = Callable[..., CheckResult]

CHECK_ID = "knip-config"

_PKG_NO_KNIP = '{"name": "demo"}'
_PKG_INLINE_KNIP = '{"name": "demo", "knip": {"ignoreBinaries": ["uv"]}}'

_BASE_ALLOWED = (
    '{"$schema": "https://unpkg.com/knip@6/schema.json", '
    '"ignoreBinaries": ["podman", "uv"], "ignoreDependencies": ["cloudflare"]}'
)
_BASE_EXTRA_KEY = '{"ignoreBinaries": ["uv"], "entry": ["src/main.ts"]}'
_BASE_NOT_A_LIST = '{"ignoreBinaries": "uv"}'
_BASE_BINARY_OUTSIDE_ALLOWANCE = '{"ignoreBinaries": ["uv", "terraform"]}'
_BASE_DEPENDENCY_OUTSIDE_ALLOWANCE = '{"ignoreDependencies": ["cloudflare", "left-pad"]}'

_ENTRY_EXPORTS_OK = '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"]}'
_ENTRY_EXPORTS_NOT_TRUE = '{"includeEntryExports": false, "ignoreWorkspaces": ["tests/*"]}'
_ENTRY_EXPORTS_WRONG_IGNORE = '{"includeEntryExports": true, "ignoreWorkspaces": ["test/*"]}'
_ENTRY_EXPORTS_STRAY_KEY = '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], "extra": true}'
_ENTRY_EXPORTS_MISSING_OVERRIDE = _ENTRY_EXPORTS_OK
_ENTRY_EXPORTS_EXTRA_OVERRIDE = (
    '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], '
    '"workspaces": {"packages/other": {"includeEntryExports": false}}}'
)
_ENTRY_EXPORTS_CORRECT_WITH_TARGET = (
    '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], '
    '"workspaces": {"packages/lib": {"includeEntryExports": false}}}'
)
_ENTRY_EXPORTS_MALFORMED_WORKSPACE_ENTRY = (
    '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], '
    '"workspaces": {"packages/lib": {"includeEntryExports": false, "entry": "src/other.ts"}}}'
)
_ENTRY_EXPORTS_WORKSPACES_NOT_AN_OBJECT = (
    '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], "workspaces": []}'
)
_ENTRY_EXPORTS_EXCLUDE_CATALOG = (
    '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], "exclude": ["catalog"]}'
)
_ENTRY_EXPORTS_EXCLUDE_TOO_MUCH = (
    '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], "exclude": ["catalog", "exports"]}'
)
_ENTRY_EXPORTS_WITH_ALLOWANCES = (
    '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], '
    '"ignoreBinaries": ["podman", "uv"], "ignoreDependencies": ["cloudflare"]}'
)

_RELEASE_TARGETS_ONE_NPM = (
    "[[target]]\n"
    'kind = "npm"\n'
    'label = "@demo/lib"\n'
    'tag_prefix = "lib-v"\n'
    'version = { file = "packages/lib/package.json", json = "version" }\n'
    'surface = ["packages/lib"]\n'
)
_RELEASE_TARGETS_MIXED_KINDS = (
    _RELEASE_TARGETS_ONE_NPM + "\n"
    "[[target]]\n"
    'kind = "pypi"\n'
    'label = "demo-tool"\n'
    'tag_prefix = "tool-v"\n'
    'version = { file = "tool/pyproject.toml", regex = \'^version = "([^"]+)"\' }\n'
    'surface = ["tool"]\n'
)

_OK = "knip.json (if any) stays within the shared allowances; knip.prod.json exactly exempts every published npm target"


@pytest.fixture
def run_knip_config(run_check_with_files: RunCheckWithFiles) -> RunKnipConfig:
    def _run(
        *,
        package_json: str | None = _PKG_NO_KNIP,
        knip: str | None = None,
        prod: str | None = None,
        release_targets: str | None = None,
    ) -> CheckResult:
        files = {
            "package.json": package_json,
            "knip.json": knip,
            "knip.prod.json": prod,
            "release-targets.toml": release_targets,
        }
        return run_check_with_files(CHECK_ID, {path: content for path, content in files.items() if content is not None})

    return _run


def test_27_1_1_skips_repos_with_no_package_json(run_knip_config: RunKnipConfig, skip: MakeFinding) -> None:
    result = run_knip_config(package_json=None)
    assert result.findings == [skip("no package.json")]


def test_27_1_2_errors_when_package_json_cannot_be_parsed(run_knip_config: RunKnipConfig, status: type[Status]) -> None:
    result = run_knip_config(package_json="{unterminated")
    assert result.findings[0].status == status.ERROR
    assert result.findings[0].message.startswith("could not parse package.json:")


def test_27_1_3_errors_when_package_json_is_not_an_object(run_knip_config: RunKnipConfig, error: MakeFinding) -> None:
    result = run_knip_config(package_json="[]")
    assert result.findings == [error("package.json must be a JSON object")]


def test_27_2_1_fails_when_package_json_has_an_inline_knip_key(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(package_json=_PKG_INLINE_KNIP, prod=_ENTRY_EXPORTS_OK)
    assert (
        fail('package.json must not have a "knip" key; move its content to a standalone knip.json') in result.findings
    )


def test_27_3_1_fails_when_knip_json_customizes_anything_beyond_the_allowed_keys(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(knip=_BASE_EXTRA_KEY, prod=_ENTRY_EXPORTS_OK)
    assert (
        fail(
            'knip.json may only customize "ignoreBinaries", "ignoreDependencies"; unexpected key(s): entry',
        )
        in result.findings
    )


def test_27_3_2_fails_when_an_allowed_key_is_not_a_list_of_strings(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(knip=_BASE_NOT_A_LIST, prod=_ENTRY_EXPORTS_OK)
    assert fail('knip.json "ignoreBinaries" must be a JSON array of strings') in result.findings


def test_27_3_3_fails_when_ignore_binaries_names_a_binary_outside_the_shared_allowance(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(knip=_BASE_BINARY_OUTSIDE_ALLOWANCE, prod=_ENTRY_EXPORTS_OK)
    assert fail("knip.json ignoreBinaries allows only podman, uv; not allowed: terraform") in result.findings


def test_27_3_4_fails_when_ignore_dependencies_names_a_dependency_outside_the_shared_allowance(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(knip=_BASE_DEPENDENCY_OUTSIDE_ALLOWANCE, prod=_ENTRY_EXPORTS_OK)
    assert fail("knip.json ignoreDependencies allows only cloudflare; not allowed: left-pad") in result.findings


def test_27_3_5_passes_when_customizations_draw_only_from_the_shared_allowances_ignoring_schema(
    run_knip_config: RunKnipConfig, ok: MakeFinding
) -> None:
    result = run_knip_config(knip=_BASE_ALLOWED, prod=_ENTRY_EXPORTS_WITH_ALLOWANCES)
    assert result.findings == [ok(_OK)]


def test_27_3_6_passes_when_knip_json_is_absent_and_the_repo_needs_no_customization(
    run_knip_config: RunKnipConfig, ok: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_OK)
    assert result.findings == [ok(_OK)]


def test_27_3_7_errors_when_knip_json_cannot_be_parsed(run_knip_config: RunKnipConfig, status: type[Status]) -> None:
    result = run_knip_config(knip="{unterminated", prod=_ENTRY_EXPORTS_OK)
    assert result.findings[0].status == status.ERROR
    assert result.findings[0].message.startswith("could not parse knip.json:")


def test_27_3_8_errors_when_knip_json_is_not_an_object(run_knip_config: RunKnipConfig, error: MakeFinding) -> None:
    result = run_knip_config(knip="[]", prod=_ENTRY_EXPORTS_OK)
    assert error("knip.json must be a JSON object") in result.findings


def test_27_4_1_fails_when_knip_prod_json_is_missing(run_knip_config: RunKnipConfig, fail: MakeFinding) -> None:
    result = run_knip_config()
    assert result.findings == [fail("no knip.prod.json at repo root — needed to catch dead/test-only exports")]


def test_27_4_2_fails_when_include_entry_exports_is_not_true(run_knip_config: RunKnipConfig, fail: MakeFinding) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_NOT_TRUE)
    assert fail('knip.prod.json must set "includeEntryExports": true') in result.findings


def test_27_4_3_fails_when_ignore_workspaces_does_not_match_the_test_harness_glob(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_WRONG_IGNORE)
    assert fail('knip.prod.json must set "ignoreWorkspaces": ["tests/*"]') in result.findings


def test_27_4_4_fails_and_names_an_unexpected_top_level_key(run_knip_config: RunKnipConfig, fail: MakeFinding) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_STRAY_KEY)
    assert fail("knip.prod.json has unexpected key(s): extra") in result.findings


def test_27_4_5_fails_and_names_a_published_target_missing_its_exemption(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_MISSING_OVERRIDE, release_targets=_RELEASE_TARGETS_ONE_NPM)
    assert fail("knip.prod.json workspaces must exempt published target(s): packages/lib") in result.findings


def test_27_4_6_fails_and_names_a_non_published_dir_wrongly_exempted(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_EXTRA_OVERRIDE)
    assert fail("knip.prod.json workspaces exempts non-published dir(s): packages/other") in result.findings


def test_27_4_7_passes_when_every_published_npm_target_is_exempted_and_nothing_else_is(
    run_knip_config: RunKnipConfig, ok: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_CORRECT_WITH_TARGET, release_targets=_RELEASE_TARGETS_ONE_NPM)
    assert result.findings == [ok(_OK)]


def test_27_4_8_passes_with_no_release_targets_toml_and_no_workspace_exemptions(
    run_knip_config: RunKnipConfig, ok: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_OK)
    assert result.findings == [ok(_OK)]


def test_27_4_9_errors_when_knip_prod_json_cannot_be_parsed(
    run_knip_config: RunKnipConfig, status: type[Status]
) -> None:
    result = run_knip_config(prod="{unterminated")
    assert result.findings[0].status == status.ERROR
    assert result.findings[0].message.startswith("could not parse knip.prod.json:")


def test_27_4_10_errors_when_knip_prod_json_is_not_an_object(
    run_knip_config: RunKnipConfig, error: MakeFinding
) -> None:
    result = run_knip_config(prod="[]")
    assert error("knip.prod.json must be a JSON object") in result.findings


def test_27_4_11_ignores_a_malformed_release_targets_toml_as_no_published_targets(
    run_knip_config: RunKnipConfig, ok: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_OK, release_targets="not = [valid")
    assert result.findings == [ok(_OK)]


def test_27_4_12_ignores_a_release_targets_toml_whose_target_key_is_not_a_list(
    run_knip_config: RunKnipConfig, ok: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_OK, release_targets='target = "not-a-list"\n')
    assert result.findings == [ok(_OK)]


def test_27_4_13_ignores_non_npm_targets_when_computing_published_workspace_dirs(
    run_knip_config: RunKnipConfig, ok: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_CORRECT_WITH_TARGET, release_targets=_RELEASE_TARGETS_MIXED_KINDS)
    assert result.findings == [ok(_OK)]


def test_27_4_14_requires_the_prod_config_to_repeat_knip_jsons_customizations(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(knip=_BASE_ALLOWED, prod=_ENTRY_EXPORTS_OK)
    assert fail('knip.prod.json must set "ignoreBinaries": ["podman", "uv"]') in result.findings
    assert fail('knip.prod.json must set "ignoreDependencies": ["cloudflare"]') in result.findings


def test_27_4_15_passes_when_the_prod_config_repeats_knip_jsons_customizations(
    run_knip_config: RunKnipConfig, ok: MakeFinding
) -> None:
    result = run_knip_config(knip=_BASE_ALLOWED, prod=_ENTRY_EXPORTS_WITH_ALLOWANCES)
    assert result.findings == [ok(_OK)]


def test_27_4_16_fails_and_names_a_workspace_entry_with_extra_keys(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_MALFORMED_WORKSPACE_ENTRY, release_targets=_RELEASE_TARGETS_ONE_NPM)
    assert (
        fail(
            'knip.prod.json workspaces entries must be exactly {"includeEntryExports": false}: packages/lib',
        )
        in result.findings
    )


def test_27_4_17_fails_when_the_workspaces_key_is_not_an_object(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_WORKSPACES_NOT_AN_OBJECT)
    assert fail('knip.prod.json "workspaces" must be a JSON object') in result.findings


def test_27_4_18_allows_excluding_exactly_the_catalog_issue_type(
    run_knip_config: RunKnipConfig, ok: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_EXCLUDE_CATALOG)
    assert result.findings == [ok(_OK)]


def test_27_4_19_fails_when_exclude_covers_anything_beyond_the_catalog_issue_type(
    run_knip_config: RunKnipConfig, fail: MakeFinding
) -> None:
    result = run_knip_config(prod=_ENTRY_EXPORTS_EXCLUDE_TOO_MUCH)
    assert fail('knip.prod.json "exclude" (if any) must be exactly ["catalog"]') in result.findings
