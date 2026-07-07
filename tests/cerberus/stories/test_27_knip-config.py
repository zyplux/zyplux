from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.context import Context
    from cerberus.model import CheckResult, Finding, Repo, Status

type RunCheck = Callable[[str, Repo, Context], CheckResult]
type RunKnipConfig = Callable[..., CheckResult]

CHECK_ID = "knip-config"

_PKG_NO_KNIP = '{"name": "demo"}'
_PKG_INLINE_KNIP = '{"name": "demo", "knip": {"ignoreBinaries": ["uv"]}}'

_BASE_MATCHING = '{"$schema": "https://unpkg.com/knip@6/schema.json", "ignoreBinaries": ["podman", "uv"]}'
_BASE_WRONG = '{"ignoreBinaries": ["uv"]}'

_ENTRY_EXPORTS_OK = '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"]}'
_ENTRY_EXPORTS_NOT_TRUE = '{"includeEntryExports": false, "ignoreWorkspaces": ["tests/*"]}'
_ENTRY_EXPORTS_WRONG_IGNORE = '{"includeEntryExports": true, "ignoreWorkspaces": ["test/*"]}'
_ENTRY_EXPORTS_STRAY_KEY = '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], "extra": true}'
_ENTRY_EXPORTS_MISSING_OVERRIDE = _ENTRY_EXPORTS_OK
_ENTRY_EXPORTS_EXTRA_OVERRIDE = (
    '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], "workspaces": {"packages/other": {"includeEntryExports": false}}}'
)
_ENTRY_EXPORTS_CORRECT_WITH_TARGET = (
    '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], "workspaces": {"packages/lib": {"includeEntryExports": false}}}'
)
_ENTRY_EXPORTS_MALFORMED_WORKSPACE_ENTRY = (
    '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], "workspaces": {"packages/lib": {"includeEntryExports": false, "entry": "src/other.ts"}}}'
)
_ENTRY_EXPORTS_WORKSPACES_NOT_AN_OBJECT = '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], "workspaces": []}'
_ENTRY_EXPORTS_ZYPLUX = '{"includeEntryExports": true, "ignoreWorkspaces": ["tests/*"], "ignoreBinaries": ["podman", "uv"]}'

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

_OK = "knip.json (if any) matches the repo's allowlisted config; knip.prod.json exactly exempts every published npm target"


@pytest.fixture
def run_knip_config(ctx: Context, run_check: RunCheck, repo_class: type[Repo], monkeypatch: pytest.MonkeyPatch) -> RunKnipConfig:
    def _run(files: dict[str, str], *, repo_name: str = "demo") -> CheckResult:
        repo = repo_class(repo_name)
        monkeypatch.setattr(ctx, "paths", lambda _repo: sorted(files))
        monkeypatch.setattr(ctx, "file", lambda _repo, path: files.get(path))
        return run_check(CHECK_ID, repo, ctx)

    return _run


def test_27_1_1_skips_repos_with_no_package_json(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({})
    assert result.findings == [finding(status.SKIP, "no package.json")]


def test_27_1_2_errors_when_package_json_cannot_be_parsed(run_knip_config: RunKnipConfig, status: type[Status]) -> None:
    result = run_knip_config({"package.json": "{unterminated"})
    assert result.findings[0].status == status.ERROR
    assert result.findings[0].message.startswith("could not parse package.json:")


def test_27_1_3_errors_when_package_json_is_not_an_object(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({"package.json": "[]"})
    assert result.findings == [finding(status.ERROR, "package.json must be a JSON object")]


def test_27_2_1_fails_when_package_json_has_an_inline_knip_key(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({
        "package.json": _PKG_INLINE_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_OK,
    })
    assert finding(status.FAIL, 'package.json must not have a "knip" key; move its content to a standalone knip.json') in result.findings


def test_27_3_1_fails_when_knip_json_is_present_but_the_repo_has_no_allowlisted_config(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.json": _BASE_WRONG,
        "knip.prod.json": _ENTRY_EXPORTS_OK,
    })
    assert finding(status.FAIL, "knip.json present but demo has no allowlisted customization; remove it or allowlist it") in result.findings


def test_27_3_2_fails_when_knip_json_does_not_match_the_repos_allowlisted_config(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config(
        {
            "package.json": _PKG_NO_KNIP,
            "knip.json": _BASE_WRONG,
            "knip.prod.json": _ENTRY_EXPORTS_OK,
        },
        repo_name="zyplux",
    )
    assert finding(status.FAIL, "knip.json does not match the allowlisted config for zyplux") in result.findings


def test_27_3_3_passes_when_knip_json_matches_the_repos_allowlisted_config_ignoring_schema(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config(
        {
            "package.json": _PKG_NO_KNIP,
            "knip.json": _BASE_MATCHING,
            "knip.prod.json": _ENTRY_EXPORTS_ZYPLUX,
        },
        repo_name="zyplux",
    )
    assert result.findings == [finding(status.PASS, _OK)]


def test_27_3_4_passes_when_knip_json_is_absent_and_the_repo_needs_no_customization(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_OK,
    })
    assert result.findings == [finding(status.PASS, _OK)]


def test_27_3_5_errors_when_knip_json_cannot_be_parsed(run_knip_config: RunKnipConfig, status: type[Status]) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.json": "{unterminated",
        "knip.prod.json": _ENTRY_EXPORTS_OK,
    })
    assert result.findings[0].status == status.ERROR
    assert result.findings[0].message.startswith("could not parse knip.json:")


def test_27_3_6_errors_when_knip_json_is_not_an_object(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.json": "[]",
        "knip.prod.json": _ENTRY_EXPORTS_OK,
    })
    assert finding(status.ERROR, "knip.json must be a JSON object") in result.findings


def test_27_4_1_fails_when_knip_prod_json_is_missing(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({"package.json": _PKG_NO_KNIP})
    assert result.findings == [finding(status.FAIL, "no knip.prod.json at repo root — needed to catch dead/test-only exports")]


def test_27_4_2_fails_when_include_entry_exports_is_not_true(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_NOT_TRUE,
    })
    assert finding(status.FAIL, 'knip.prod.json must set "includeEntryExports": true') in result.findings


def test_27_4_3_fails_when_ignore_workspaces_does_not_match_the_test_harness_glob(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_WRONG_IGNORE,
    })
    assert finding(status.FAIL, 'knip.prod.json must set "ignoreWorkspaces": ["tests/*"]') in result.findings


def test_27_4_4_fails_and_names_an_unexpected_top_level_key(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_STRAY_KEY,
    })
    assert finding(status.FAIL, "knip.prod.json has unexpected key(s): extra") in result.findings


def test_27_4_5_fails_and_names_a_published_target_missing_its_exemption(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_MISSING_OVERRIDE,
        "release-targets.toml": _RELEASE_TARGETS_ONE_NPM,
    })
    assert finding(status.FAIL, "knip.prod.json workspaces must exempt published target(s): packages/lib") in result.findings


def test_27_4_6_fails_and_names_a_non_published_dir_wrongly_exempted(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_EXTRA_OVERRIDE,
    })
    assert finding(status.FAIL, "knip.prod.json workspaces exempts non-published dir(s): packages/other") in result.findings


def test_27_4_7_passes_when_every_published_npm_target_is_exempted_and_nothing_else_is(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_CORRECT_WITH_TARGET,
        "release-targets.toml": _RELEASE_TARGETS_ONE_NPM,
    })
    assert result.findings == [finding(status.PASS, _OK)]


def test_27_4_8_passes_with_no_release_targets_toml_and_no_workspace_exemptions(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_OK,
    })
    assert result.findings == [finding(status.PASS, _OK)]


def test_27_4_9_errors_when_knip_prod_json_cannot_be_parsed(run_knip_config: RunKnipConfig, status: type[Status]) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": "{unterminated",
    })
    assert result.findings[0].status == status.ERROR
    assert result.findings[0].message.startswith("could not parse knip.prod.json:")


def test_27_4_10_errors_when_knip_prod_json_is_not_an_object(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": "[]",
    })
    assert finding(status.ERROR, "knip.prod.json must be a JSON object") in result.findings


def test_27_4_11_ignores_a_malformed_release_targets_toml_as_no_published_targets(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_OK,
        "release-targets.toml": "not = [valid",
    })
    assert result.findings == [finding(status.PASS, _OK)]


def test_27_4_12_ignores_a_release_targets_toml_whose_target_key_is_not_a_list(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_OK,
        "release-targets.toml": 'target = "not-a-list"\n',
    })
    assert result.findings == [finding(status.PASS, _OK)]


def test_27_4_13_ignores_non_npm_targets_when_computing_published_workspace_dirs(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_CORRECT_WITH_TARGET,
        "release-targets.toml": _RELEASE_TARGETS_MIXED_KINDS,
    })
    assert result.findings == [finding(status.PASS, _OK)]


def test_27_4_14_requires_the_prod_config_to_repeat_the_repos_allowlisted_base_config(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config(
        {
            "package.json": _PKG_NO_KNIP,
            "knip.json": _BASE_MATCHING,
            "knip.prod.json": _ENTRY_EXPORTS_OK,
        },
        repo_name="zyplux",
    )
    assert finding(status.FAIL, 'knip.prod.json must set "ignoreBinaries": ["podman", "uv"]') in result.findings


def test_27_4_15_passes_when_the_prod_config_repeats_the_repos_allowlisted_base_config(
    run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]
) -> None:
    result = run_knip_config(
        {
            "package.json": _PKG_NO_KNIP,
            "knip.json": _BASE_MATCHING,
            "knip.prod.json": _ENTRY_EXPORTS_ZYPLUX,
        },
        repo_name="zyplux",
    )
    assert result.findings == [finding(status.PASS, _OK)]


def test_27_4_16_fails_and_names_a_workspace_entry_with_extra_keys(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_MALFORMED_WORKSPACE_ENTRY,
        "release-targets.toml": _RELEASE_TARGETS_ONE_NPM,
    })
    assert (
        finding(
            status.FAIL,
            'knip.prod.json workspaces entries must be exactly {"includeEntryExports": false}: packages/lib',
        )
        in result.findings
    )


def test_27_4_17_fails_when_the_workspaces_key_is_not_an_object(run_knip_config: RunKnipConfig, finding: type[Finding], status: type[Status]) -> None:
    result = run_knip_config({
        "package.json": _PKG_NO_KNIP,
        "knip.prod.json": _ENTRY_EXPORTS_WORKSPACES_NOT_AN_OBJECT,
    })
    assert finding(status.FAIL, 'knip.prod.json "workspaces" must be a JSON object') in result.findings
