from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo
    from cerberus.source import GitHistoryUnavailableError
    from seam_fixtures import MakeFinding, RunCheck


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


class RegistryDouble(Protocol):
    """The shape of the registry lookup test double `fake_registry` hands back.

    A structural type, not a nominal import of the concrete class conftest.py
    builds — keeps this file free of any dependency on where that class lives.
    """

    not_found: set[tuple[str, str]]

    def serve_npm(self, package: str, latest: str) -> None: ...
    def serve_pypi(self, distribution: str, latest: str) -> None: ...
    def serve_npm_missing(self, package: str) -> None: ...
    def serve_pypi_missing(self, distribution: str) -> None: ...


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


@pytest.fixture
def run_release_bumps(
    monkeypatch: pytest.MonkeyPatch,
    repo: Repo,
    ctx: Context,
    run_check: RunCheck,
    fake_registry: RegistryDouble,
) -> RunReleaseBumps:
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
        monkeypatch.setattr(ctx, "file", lambda _repo, path: files.get(path))

        is_pypi = "pypi" in (manifest or "")
        package = "zyplux-widget" if is_pypi else "@zyplux/widget"
        if published == UNREACHABLE:
            pass
        elif published is None:
            fake_registry.serve_pypi_missing(package) if is_pypi else fake_registry.serve_npm_missing(package)
        elif is_pypi:
            fake_registry.serve_pypi(package, published)
        else:
            fake_registry.serve_npm(package, published)

        def read_changed(*_: object) -> list[str]:
            if isinstance(changed, Exception):
                raise changed
            return list(changed)

        monkeypatch.setattr(ctx, "changed_paths", read_changed)
        return run_check(CHECK_ID, repo, ctx)

    return run


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


def test_14_4_1_passes_when_the_current_version_is_ahead_of_the_latest_published_release(
    run_release_bumps: RunReleaseBumps, ok: MakeFinding
) -> None:
    result = run_release_bumps(version_file_content=version_json("0.2.0"), published="0.1.0", changed=[])
    assert result.findings == [
        ok(f"{LABEL}: 0.2.0 is ahead of published 0.1.0"),
        ok(DONE),
    ]


def test_14_4_2_fails_when_the_current_version_trails_the_latest_published_release(
    run_release_bumps: RunReleaseBumps, fail: MakeFinding
) -> None:
    result = run_release_bumps(published="0.2.0", changed=[])
    assert result.findings == [fail(f"{LABEL}: version 0.1.0 is below published 0.2.0")]


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
