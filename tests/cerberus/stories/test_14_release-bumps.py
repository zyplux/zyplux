from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from cerberus.context import Context
    from cerberus.model import CheckResult, Finding, Repo, Status
    from cerberus.source import GitHistoryUnavailableError

type RunCheck = Callable[[str, Repo, Context], CheckResult]

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
CHECK_ID = "release-bumps"


def version_json(version: str) -> str:
    return f'{{"version": "{version}"}}'


class RunReleaseBumps(Protocol):
    def __call__(
        self,
        *,
        manifest: str | None = ...,
        version_file_content: str | None = ...,
        version_path: str = ...,
        tags: Sequence[str] | Exception = ...,
        changed: Sequence[str] | Exception = ...,
    ) -> CheckResult: ...


@pytest.fixture
def run_release_bumps(monkeypatch: pytest.MonkeyPatch, repo: Repo, ctx: Context, run_check: RunCheck) -> RunReleaseBumps:
    def run(
        *,
        manifest: str | None = MANIFEST,
        version_file_content: str | None = version_json("0.1.0"),
        version_path: str = VERSION_FILE,
        tags: Sequence[str] | Exception = (),
        changed: Sequence[str] | Exception = (),
    ) -> CheckResult:
        files: dict[str, str] = {}
        if manifest is not None:
            files["release-targets.toml"] = manifest
        if version_file_content is not None:
            files[version_path] = version_file_content
        monkeypatch.setattr(ctx, "file", lambda _repo, path: files.get(path))

        def read_tags(*_: object) -> list[str]:
            if isinstance(tags, Exception):
                raise tags
            return list(tags)

        def read_changed(*_: object) -> list[str]:
            if isinstance(changed, Exception):
                raise changed
            return list(changed)

        monkeypatch.setattr(ctx, "tags", read_tags)
        monkeypatch.setattr(ctx, "changed_paths", read_changed)
        return run_check(CHECK_ID, repo, ctx)

    return run


def test_14_1_1_skips_repos_that_publish_nothing(run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]) -> None:
    result = run_release_bumps(manifest=None)
    assert result.findings == [finding(status.SKIP, "no release-targets.toml — repo publishes nothing")]


def test_14_1_2_errors_when_the_release_manifest_is_malformed(run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]) -> None:
    result = run_release_bumps(manifest=MALFORMED_MANIFEST)
    assert result.findings == [finding(status.ERROR, "release-targets.toml is malformed: Invalid value (at line 1, column 7)")]


def test_14_1_3_errors_when_the_manifest_has_no_target_array(run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]) -> None:
    result = run_release_bumps(manifest="")
    assert result.findings == [
        finding(
            status.ERROR,
            "release-targets.toml is malformed: release-targets.toml has no [[target]] array (found None)",
        )
    ]


def test_14_2_1_fails_when_the_version_file_is_missing(run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]) -> None:
    result = run_release_bumps(version_file_content=None)
    assert result.findings == [finding(status.FAIL, f"{LABEL}: version file {VERSION_FILE} is missing")]


def test_14_2_2_fails_when_the_version_file_is_not_valid_json(run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]) -> None:
    result = run_release_bumps(version_file_content="not json")
    assert result.findings == [
        finding(
            status.FAIL,
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
    run_release_bumps: RunReleaseBumps,
    manifest: str,
    version_file_content: str,
    finding: type[Finding],
    status: type[Status],
) -> None:
    result = run_release_bumps(manifest=manifest, version_file_content=version_file_content)
    assert result.findings == [finding(status.FAIL, f"{LABEL}: no version found in {VERSION_FILE}")]


def test_14_2_4_fails_when_the_declared_version_is_not_semver(run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]) -> None:
    result = run_release_bumps(version_file_content=version_json("not-a-version"))
    assert result.findings == [finding(status.FAIL, f"{LABEL}: version 'not-a-version' is not semver")]


def test_14_2_5_reads_the_version_via_the_target_regex(run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]) -> None:
    result = run_release_bumps(
        manifest=REGEX_MANIFEST,
        version_path="apps/widget/pyproject.toml",
        version_file_content='[project]\nname = "widget"\nversion = "0.2.0"\n',
        tags=["widget-v0.1.0"],
        changed=[],
    )
    assert result.findings == [
        finding(status.PASS, "zyplux-widget: 0.2.0 is ahead of published 0.1.0"),
        finding(status.PASS, DONE),
    ]


def test_14_3_1_treats_a_target_with_no_published_tags_as_not_yet_released(
    run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]
) -> None:
    result = run_release_bumps(tags=[])
    assert result.findings == [
        finding(status.PASS, f"{LABEL}: not yet released"),
        finding(status.PASS, DONE),
    ]


def test_14_3_2_picks_the_highest_semver_tag_and_ignores_tags_that_are_not_semver(
    run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]
) -> None:
    result = run_release_bumps(
        version_file_content=version_json("0.2.0"),
        tags=["widget-v0.2.0", "widget-v0.10.0", "widget-vnext"],
        changed=[],
    )
    assert result.findings == [finding(status.FAIL, f"{LABEL}: version 0.2.0 is below published 0.10.0 (widget-v0.10.0)")]


def test_14_3_3_errors_when_the_published_tags_cannot_be_read(
    run_release_bumps: RunReleaseBumps,
    finding: type[Finding],
    status: type[Status],
    git_history_unavailable_error: type[GitHistoryUnavailableError],
) -> None:
    result = run_release_bumps(tags=git_history_unavailable_error("git tag failed"))
    assert result.findings == [finding(status.ERROR, f"{LABEL}: cannot read git tags: git tag failed")]


def test_14_4_1_passes_when_the_current_version_is_ahead_of_the_latest_published_release(
    run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]
) -> None:
    result = run_release_bumps(version_file_content=version_json("0.2.0"), tags=["widget-v0.1.0"], changed=[])
    assert result.findings == [
        finding(status.PASS, f"{LABEL}: 0.2.0 is ahead of published 0.1.0"),
        finding(status.PASS, DONE),
    ]


def test_14_4_2_fails_when_the_current_version_trails_the_latest_published_release(
    run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]
) -> None:
    result = run_release_bumps(tags=["widget-v0.2.0"], changed=[])
    assert result.findings == [finding(status.FAIL, f"{LABEL}: version 0.1.0 is below published 0.2.0 (widget-v0.2.0)")]


def test_14_5_1_passes_when_the_release_surface_is_unchanged_since_the_latest_release(
    run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]
) -> None:
    result = run_release_bumps(tags=["widget-v0.1.0"], changed=[])
    assert result.findings == [finding(status.PASS, DONE)]


def test_14_5_2_fails_and_names_the_required_bump_when_the_surface_changed_without_one(
    run_release_bumps: RunReleaseBumps, finding: type[Finding], status: type[Status]
) -> None:
    result = run_release_bumps(tags=["widget-v0.1.0"], changed=["packages/widget/src/a.ts"])
    assert result.findings == [
        finding(
            status.FAIL,
            f"{LABEL}: surface changed since widget-v0.1.0 but version is still 0.1.0 — bump it (e.g. 0.1.1)",
        )
    ]


def test_14_5_3_errors_when_the_surface_diff_cannot_be_computed(
    run_release_bumps: RunReleaseBumps,
    finding: type[Finding],
    status: type[Status],
    git_history_unavailable_error: type[GitHistoryUnavailableError],
) -> None:
    result = run_release_bumps(tags=["widget-v0.1.0"], changed=git_history_unavailable_error("git diff failed"))
    assert result.findings == [finding(status.ERROR, f"{LABEL}: cannot diff against widget-v0.1.0: git diff failed")]
