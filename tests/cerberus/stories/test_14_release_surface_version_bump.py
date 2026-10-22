from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo
    from cerberus.source import GitHistoryUnavailableError
    from seam_fixtures import FakeRegistry, MakeFinding, RunCheck


MANIFEST = """
[[target]]
kind = "npm"
label = "@zyplux/widget"
tag_prefix = "widget-v"
version = { file = "packages/widget/package.json", json = "version" }
surface = ["packages/widget/src"]
"""

REGEX_MANIFEST = """
[[target]]
kind = "pypi"
label = "zyplux-widget"
tag_prefix = "widget-v"
version = { file = "apps/widget/pyproject.toml", regex = '^version = "([^"]+)"' }
surface = ["apps/widget/src"]
"""

MALFORMED_MANIFEST = "not = valid = toml"
VERSION_FILE = "packages/widget/package.json"
LABEL = "@zyplux/widget"
DONE = "every published target's version tracks its surface"
CHECK_ID = "release_surface_version_bump"


def version_json(version: str) -> str:
    return f'{{"version": "{version}"}}'


UNREACHABLE = "unreachable"


class RunReleaseBumps(Protocol):
    def __call__(
        self,
        *,
        manifest: str | None = ...,
        version_file_content: str | None = ...,
        version_path: str = ...,
        published: str | None = ...,
        changed: Sequence[str] | Exception = ...,
    ) -> CheckResult: ...


class ConfigureBase(Protocol):
    def __call__(self, content: str | Exception | None, *, manifest: str | None = ...) -> None: ...


@pytest.fixture
def target_branch(monkeypatch: pytest.MonkeyPatch, ctx: Context, run_release_bumps: RunReleaseBumps) -> ConfigureBase:
    del run_release_bumps

    def configure(content: str | Exception | None, *, manifest: str | None = MANIFEST) -> None:
        monkeypatch.setenv("GITHUB_BASE_REF", "main")

        def read_base(_repo: Repo, _ref: str, path: str) -> str | None:
            if isinstance(content, Exception):
                raise content
            return {"release-targets.toml": manifest, VERSION_FILE: content}.get(path)

        monkeypatch.setattr(ctx, "file_at_ref", read_base)

    return configure


def serve_release(registry: FakeRegistry, manifest: str | None, version: str | None, published: str | None) -> None:
    is_pypi = "pypi" in (manifest or "")
    package = "zyplux-widget" if is_pypi else "@zyplux/widget"
    host = "npm.pkg.github.com" if "npm.pkg.github.com" in (version or "") else "registry.npmjs.org"
    if published == UNREACHABLE:
        return
    if published is None:
        registry.serve_pypi_missing(package) if is_pypi else registry.serve_npm_missing(package, host=host)
    elif is_pypi:
        registry.serve_pypi(package, published)
    else:
        registry.serve_npm(package, published, host=host)


@pytest.fixture
def run_release_bumps(
    monkeypatch: pytest.MonkeyPatch,
    repo: Repo,
    ctx: Context,
    run_check: RunCheck,
    fake_registry: FakeRegistry,
) -> RunReleaseBumps:
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)

    def run(
        *,
        manifest: str | None = MANIFEST,
        version_file_content: str | None = version_json("0.1.0"),
        version_path: str = VERSION_FILE,
        published: str | None = None,
        changed: Sequence[str] | Exception = (),
    ) -> CheckResult:
        files: dict[str, str] = {}
        if manifest is not None:
            files["release-targets.toml"] = manifest
        if version_file_content is not None:
            files[version_path] = version_file_content

        def read_file(_repo: Repo, path: str) -> str | None:
            return files.get(path)

        monkeypatch.setattr(ctx, "file", read_file)
        serve_release(fake_registry, manifest, version_file_content, published)

        def read_changed(_repo: Repo, _ref: str, _surface: Sequence[str]) -> list[str]:
            if isinstance(changed, Exception):
                raise changed
            return list(changed)

        monkeypatch.setattr(ctx, "changed_paths", read_changed)
        return run_check(CHECK_ID, repo, ctx)

    return run


def private_version_json(version: str) -> str:
    return json.dumps({"version": version, "publishConfig": {"registry": "https://npm.pkg.github.com"}})


def test_14_1_1_skips_repos_that_publish_nothing(run_release_bumps: RunReleaseBumps, skip: MakeFinding) -> None:
    result = run_release_bumps(manifest=None)
    assert result.findings == [skip("no release-targets.toml — repo publishes nothing")]


def test_14_1_2_errors_when_the_release_manifest_is_malformed(
    run_release_bumps: RunReleaseBumps, error: MakeFinding
) -> None:
    result = run_release_bumps(manifest=MALFORMED_MANIFEST)
    assert result.findings == [error("release-targets.toml is malformed: Invalid value (at line 1, column 7)")]


def test_14_1_3_errors_when_the_manifest_has_no_target_array(
    run_release_bumps: RunReleaseBumps, error: MakeFinding
) -> None:
    result = run_release_bumps(manifest="")
    assert result.findings == [
        error(
            "release-targets.toml is malformed: release-targets.toml has no [[target]] array (found None)",
        )
    ]


def test_14_1_4_errors_when_a_target_has_an_unknown_kind(
    run_release_bumps: RunReleaseBumps, error: MakeFinding
) -> None:
    result = run_release_bumps(manifest=MANIFEST.replace('kind = "npm"', 'kind = "cargo"'))
    assert result.findings == [
        error(
            "release-targets.toml is malformed: target '@zyplux/widget' has unknown kind 'cargo' "
            "(expected one of ['ghcr', 'npm', 'pypi'])",
        )
    ]


def test_14_2_1_fails_when_the_version_file_is_missing(run_release_bumps: RunReleaseBumps, fail: MakeFinding) -> None:
    result = run_release_bumps(version_file_content=None)
    assert result.findings == [fail(f"{LABEL}: version file {VERSION_FILE} is missing")]


def test_14_2_2_fails_when_the_version_file_is_not_valid_json(
    run_release_bumps: RunReleaseBumps, fail: MakeFinding
) -> None:
    result = run_release_bumps(version_file_content="not json")
    assert result.findings == [
        fail(
            f"{LABEL}: {VERSION_FILE} is not valid JSON: Expecting value: line 1 column 1 (char 0)",
        )
    ]


@pytest.mark.parametrize(
    ("manifest", "version_file_content"),
    [
        (MANIFEST, '{"name": "widget"}'),
        (MANIFEST.replace('json = "version"', 'json = "metadata.version"'), '{"metadata": "widget"}'),
        (MANIFEST.replace(', json = "version"', ""), version_json("0.1.0")),
    ],
    ids=["missing_key", "non_mapping_path", "no_extractor"],
)
def test_14_2_3_fails_when_no_version_is_found_in_the_version_file(
    run_release_bumps: RunReleaseBumps, manifest: str, version_file_content: str, fail: MakeFinding
) -> None:
    result = run_release_bumps(manifest=manifest, version_file_content=version_file_content)
    assert result.findings == [fail(f"{LABEL}: no version found in {VERSION_FILE}")]


def test_14_2_4_fails_when_the_declared_version_is_not_semver(
    run_release_bumps: RunReleaseBumps, fail: MakeFinding
) -> None:
    result = run_release_bumps(version_file_content=version_json("not-a-version"))
    assert result.findings == [fail(f"{LABEL}: version 'not-a-version' is not semver")]


def test_14_2_5_reads_the_version_via_the_target_regex(run_release_bumps: RunReleaseBumps, ok: MakeFinding) -> None:
    result = run_release_bumps(
        manifest=REGEX_MANIFEST,
        version_path="apps/widget/pyproject.toml",
        version_file_content='[project]\nname = "widget"\nversion = "0.2.0"\n',
        published="0.1.0",
        changed=[],
    )
    assert result.findings == [
        ok("zyplux-widget: 0.2.0 is ahead of published 0.1.0"),
        ok(DONE),
    ]


def test_14_3_1_treats_a_target_with_nothing_published_as_not_yet_released(
    run_release_bumps: RunReleaseBumps, ok: MakeFinding
) -> None:
    result = run_release_bumps(published=None)
    assert result.findings == [
        ok(f"{LABEL}: not yet released"),
        ok(DONE),
    ]


def test_14_3_2_fails_when_the_current_version_trails_the_published_one(
    run_release_bumps: RunReleaseBumps, fail: MakeFinding
) -> None:
    result = run_release_bumps(version_file_content=version_json("0.2.0"), published="0.10.0", changed=[])
    assert result.findings == [fail(f"{LABEL}: version 0.2.0 is below published 0.10.0")]


def test_14_3_3_errors_when_the_published_version_is_not_semver(
    run_release_bumps: RunReleaseBumps, error: MakeFinding
) -> None:
    result = run_release_bumps(published="not-a-version")
    assert result.findings == [
        error(
            f"{LABEL}: cannot determine the latest published version: published version 'not-a-version' is not semver",
        )
    ]


def test_14_3_4_errors_when_the_published_version_cannot_be_determined(
    run_release_bumps: RunReleaseBumps, error: MakeFinding
) -> None:
    result = run_release_bumps(published=UNREACHABLE)
    assert result.findings == [
        error(
            f"{LABEL}: cannot determine the latest published version: "
            "https://registry.npmjs.org/@zyplux%2Fwidget: connection refused",
        )
    ]


@pytest.mark.parametrize("version", ["0.1.1", "0.2.0", "1.0.0"], ids=["patch", "minor", "major"])
def test_14_4_1_passes_when_the_current_version_is_one_step_ahead_of_the_latest_published_release(
    run_release_bumps: RunReleaseBumps, version: str, ok: MakeFinding
) -> None:
    result = run_release_bumps(version_file_content=version_json(version), published="0.1.0", changed=[])
    assert result.findings == [
        ok(f"{LABEL}: {version} is ahead of published 0.1.0"),
        ok(DONE),
    ]


def test_14_4_2_fails_when_the_current_version_trails_the_latest_published_release(
    run_release_bumps: RunReleaseBumps, fail: MakeFinding
) -> None:
    result = run_release_bumps(published="0.2.0", changed=[])
    assert result.findings == [fail(f"{LABEL}: version 0.1.0 is below published 0.2.0")]


@pytest.mark.parametrize(
    "version",
    ["0.5.2", "0.7.0", "2.0.0", "0.6.1"],
    ids=["skipped_patch", "skipped_minor", "skipped_major", "minor_with_patch"],
)
def test_14_4_3_fails_when_the_current_version_skips_ahead_of_the_latest_published_release(
    run_release_bumps: RunReleaseBumps, version: str, fail: MakeFinding
) -> None:
    result = run_release_bumps(version_file_content=version_json(version), published="0.5.0", changed=[])
    assert result.findings == [
        fail(
            f"{LABEL}: version {version} skips ahead of published 0.5.0 — bump one step (0.5.1, 0.6.0, or 1.0.0)",
        )
    ]


def test_14_5_1_passes_when_the_release_surface_is_unchanged_since_the_latest_release(
    run_release_bumps: RunReleaseBumps, ok: MakeFinding
) -> None:
    result = run_release_bumps(published="0.1.0", changed=[])
    assert result.findings == [ok(DONE)]


def test_14_5_2_fails_and_names_the_required_bump_when_the_surface_changed_without_one(
    run_release_bumps: RunReleaseBumps, fail: MakeFinding
) -> None:
    result = run_release_bumps(published="0.1.0", changed=["packages/widget/src/a.ts"])
    assert result.findings == [
        fail(
            f"{LABEL}: surface changed since widget-v0.1.0 but version is still 0.1.0 — bump it (e.g. 0.1.1)",
        )
    ]


def test_14_5_3_errors_when_the_surface_diff_cannot_be_computed(
    run_release_bumps: RunReleaseBumps,
    git_history_unavailable_error: type[GitHistoryUnavailableError],
    error: MakeFinding,
) -> None:
    result = run_release_bumps(published="0.1.0", changed=git_history_unavailable_error("git diff failed"))
    assert result.findings == [error(f"{LABEL}: cannot diff against widget-v0.1.0: git diff failed")]


def test_14_6_1_reads_a_private_github_package_using_publish_config(
    run_release_bumps: RunReleaseBumps, monkeypatch: pytest.MonkeyPatch, fake_registry: FakeRegistry, ok: MakeFinding
) -> None:
    monkeypatch.setenv("NODE_AUTH_TOKEN", "package-read-token")
    result = run_release_bumps(version_file_content=private_version_json("0.1.0"), published="0.1.0")

    assert result.findings == [ok(DONE)]
    assert fake_registry.requests == [("npm.pkg.github.com", "/@zyplux%2Fwidget")]
    assert fake_registry.request_headers == [{"Authorization": "Bearer package-read-token"}]


def test_14_6_2_errors_when_private_registry_credentials_are_missing(
    run_release_bumps: RunReleaseBumps,
    monkeypatch: pytest.MonkeyPatch,
    fake_registry: FakeRegistry,
    error: MakeFinding,
) -> None:
    monkeypatch.delenv("NODE_AUTH_TOKEN", raising=False)
    result = run_release_bumps(version_file_content=private_version_json("0.1.0"))

    assert result.findings == [
        error(
            f"{LABEL}: cannot determine the latest published version: "
            "NODE_AUTH_TOKEN is required to read npm.pkg.github.com"
        )
    ]
    assert fake_registry.requests == []


def test_14_6_3_errors_when_the_npm_registry_is_unsupported(
    run_release_bumps: RunReleaseBumps, fake_registry: FakeRegistry, error: MakeFinding
) -> None:
    result = run_release_bumps(
        version_file_content=private_version_json("0.1.0").replace("npm.pkg.github.com", "example.com")
    )

    assert result.findings == [
        error(f"{LABEL}: cannot determine the latest published version: unsupported npm registry 'https://example.com'")
    ]
    assert fake_registry.requests == []


@pytest.mark.parametrize("publish_config", [{"registry": 42}, "github"])
def test_14_6_4_errors_when_publish_config_has_no_registry_string(
    run_release_bumps: RunReleaseBumps, publish_config: object, error: MakeFinding
) -> None:
    result = run_release_bumps(version_file_content=json.dumps({"version": "0.1.0", "publishConfig": publish_config}))

    assert result.findings == [
        error(
            f"{LABEL}: cannot determine the latest published version: "
            f"{VERSION_FILE}: publishConfig.registry must be a string"
        )
    ]


@pytest.mark.parametrize("registry", ["https://registry.npmjs.org/", "https://npm.pkg.github.com/"])
def test_14_6_5_accepts_supported_registry_urls_with_a_trailing_slash(
    run_release_bumps: RunReleaseBumps, monkeypatch: pytest.MonkeyPatch, registry: str, ok: MakeFinding
) -> None:
    monkeypatch.setenv("NODE_AUTH_TOKEN", "package-read-token")
    package = {"version": "0.1.0", "publishConfig": {"registry": registry}}

    result = run_release_bumps(version_file_content=json.dumps(package), published="0.1.0")

    assert result.findings == [ok(DONE)]


@pytest.mark.parametrize(
    "publish_config",
    [
        {"@zyplux:registry": "https://npm.pkg.github.com/"},
        {"@zyplux:registry": "https://npm.pkg.github.com/", "registry": "https://registry.npmjs.org"},
    ],
    ids=["scoped_only", "scoped_overrides_default"],
)
def test_14_6_6_prefers_the_package_scopes_registry_setting(
    run_release_bumps: RunReleaseBumps,
    monkeypatch: pytest.MonkeyPatch,
    fake_registry: FakeRegistry,
    publish_config: dict[str, str],
    ok: MakeFinding,
) -> None:
    monkeypatch.setenv("NODE_AUTH_TOKEN", "package-read-token")
    package = {"version": "0.1.0", "publishConfig": publish_config}

    result = run_release_bumps(version_file_content=json.dumps(package), published="0.1.0")

    assert result.findings == [ok(DONE)]
    assert fake_registry.requests == [("npm.pkg.github.com", "/@zyplux%2Fwidget")]


def test_14_7_1_passes_when_the_release_surface_matches_the_target_branch(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, ok: MakeFinding
) -> None:
    target_branch(version_json("0.1.0"))
    result = run_release_bumps(published="0.1.0")

    assert result.findings == [ok(DONE)]


def test_14_7_2_accepts_repairs_to_an_unpublished_target_branch_version(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, ok: MakeFinding
) -> None:
    target_branch(version_json("0.1.1"))
    result = run_release_bumps(
        version_file_content=version_json("0.1.1"),
        published="0.1.0",
        changed=["packages/widget/src/a.ts"],
    )

    assert result.findings == [ok(DONE)]


def test_14_7_3_passes_when_changed_surface_has_a_new_target_branch_version(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, ok: MakeFinding
) -> None:
    target_branch(version_json("0.1.0"))
    result = run_release_bumps(
        version_file_content=version_json("0.1.1"),
        published="0.1.0",
    )

    assert result.findings == [ok(f"{LABEL}: 0.1.1 is ahead of published 0.1.0"), ok(DONE)]


def test_14_7_4_errors_when_the_target_branch_version_file_is_invalid_json(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, error: MakeFinding
) -> None:
    target_branch("invalid json")
    result = run_release_bumps(published="0.1.0")

    assert result.findings == [
        error(f"{LABEL}: cannot compare the target branch origin/main: Expecting value: line 1 column 1 (char 0)")
    ]


def test_14_7_5_accepts_a_target_introduced_by_the_pull_request(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, ok: MakeFinding
) -> None:
    target_branch(None, manifest=None)
    result = run_release_bumps()

    assert result.findings == [ok(f"{LABEL}: not yet released"), ok(DONE)]


def test_14_7_6_errors_when_target_branch_history_is_unavailable(
    run_release_bumps: RunReleaseBumps,
    git_history_unavailable_error: type[GitHistoryUnavailableError],
    target_branch: ConfigureBase,
    error: MakeFinding,
) -> None:
    target_branch(git_history_unavailable_error("git show failed"))
    result = run_release_bumps(published="0.1.0")

    assert result.findings == [error(f"{LABEL}: cannot compare the target branch origin/main: git show failed")]


def test_14_7_7_errors_when_the_target_branch_version_is_not_semver(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, error: MakeFinding
) -> None:
    target_branch(version_json("invalid"))
    result = run_release_bumps(published="0.1.0")

    assert result.findings == [error(f"{LABEL}: origin/main has no semver version")]


@pytest.mark.parametrize(("base", "version"), [("0.1.1", "0.1.2"), ("1.0.0", "1.0.1"), ("0.1.1", "0.2.0")])
def test_14_7_8_accepts_one_step_from_an_unpublished_target_branch_version(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, base: str, version: str, ok: MakeFinding
) -> None:
    target_branch(version_json(base))

    result = run_release_bumps(version_file_content=version_json(version), published="0.1.0")

    assert result.findings == [ok(f"{LABEL}: {version} is ahead of origin/main ({base})"), ok(DONE)]


def test_14_7_9_rejects_skipping_steps_from_an_unpublished_target_branch_version(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, fail: MakeFinding
) -> None:
    target_branch(version_json("0.1.1"))

    result = run_release_bumps(version_file_content=version_json("0.1.3"), published="0.1.0")

    assert result.findings == [
        fail(f"{LABEL}: version 0.1.3 skips ahead of origin/main (0.1.1) — bump one step (0.1.2, 0.2.0, or 1.0.0)")
    ]


def test_14_7_10_uses_the_published_baseline_when_it_is_newer_than_the_target_branch(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, ok: MakeFinding
) -> None:
    target_branch(version_json("0.1.0"))

    result = run_release_bumps(version_file_content=version_json("0.1.2"), published="0.1.1")

    assert result.findings == [ok(f"{LABEL}: 0.1.2 is ahead of published 0.1.1"), ok(DONE)]


def test_14_7_11_accepts_an_unchanged_unpublished_target_branch_version(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, ok: MakeFinding
) -> None:
    target_branch(version_json("1.0.0"))

    result = run_release_bumps(version_file_content=version_json("1.0.0"), published="0.1.0")

    assert result.findings == [ok(DONE)]


def test_14_7_12_accepts_one_step_before_the_first_publication(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, ok: MakeFinding
) -> None:
    target_branch(version_json("1.0.0"))

    result = run_release_bumps(version_file_content=version_json("1.0.1"))

    assert result.findings == [ok(f"{LABEL}: 1.0.1 is ahead of origin/main (1.0.0)"), ok(DONE)]


def test_14_7_13_rejects_skipping_steps_before_the_first_publication(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, fail: MakeFinding
) -> None:
    target_branch(version_json("1.0.0"))

    result = run_release_bumps(version_file_content=version_json("9.0.0"))

    assert result.findings == [
        fail(f"{LABEL}: version 9.0.0 skips ahead of origin/main (1.0.0) — bump one step (1.0.1, 1.1.0, or 2.0.0)")
    ]


def test_14_7_14_reads_the_base_version_with_its_own_extractor(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, ok: MakeFinding
) -> None:
    target_branch(version_json("0.1.0"))

    result = run_release_bumps(
        manifest=MANIFEST.replace('json = "version"', 'json = "metadata.version"'),
        version_file_content=json.dumps({"metadata": {"version": "0.1.1"}}),
        published="0.1.0",
    )

    assert result.findings == [ok(f"{LABEL}: 0.1.1 is ahead of published 0.1.0"), ok(DONE)]


def test_14_7_15_checks_the_base_version_when_its_file_moves(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, fail: MakeFinding
) -> None:
    target_branch(version_json("0.1.1"))
    moved_path = "packages/relocated/package.json"

    result = run_release_bumps(
        manifest=MANIFEST.replace(VERSION_FILE, moved_path),
        version_path=moved_path,
        version_file_content=version_json("0.1.0"),
        published="0.1.0",
    )

    assert result.findings == [fail(f"{LABEL}: version must not decrease from origin/main (0.1.1)")]


def test_14_7_16_distinguishes_targets_that_share_a_version_file(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, ok: MakeFinding
) -> None:
    target_branch(version_json("1.0.0"), manifest=MANIFEST.replace(LABEL, "@zyplux/other"))

    result = run_release_bumps()

    assert result.findings == [ok(f"{LABEL}: not yet released"), ok(DONE)]


def test_14_7_17_errors_when_an_existing_base_target_has_no_version_file(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, error: MakeFinding
) -> None:
    target_branch(None)

    result = run_release_bumps()

    assert result.findings == [
        error(f"{LABEL}: cannot compare the target branch origin/main: version file {VERSION_FILE} is missing")
    ]


def test_14_7_18_rejects_changes_to_a_published_target_branch_version(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, fail: MakeFinding
) -> None:
    target_branch(version_json("0.1.0"))

    result = run_release_bumps(published="0.1.0", changed=["packages/widget/src/a.ts"])

    assert result.findings == [
        fail(f"{LABEL}: surface changed since widget-v0.1.0 but version is still 0.1.0 — bump it (e.g. 0.1.1)")
    ]


def test_14_7_19_accepts_repairs_before_the_first_publication(
    run_release_bumps: RunReleaseBumps, target_branch: ConfigureBase, ok: MakeFinding
) -> None:
    target_branch(version_json("0.1.0"))

    result = run_release_bumps(changed=["packages/widget/src/a.ts"])

    assert result.findings == [ok(DONE)]
