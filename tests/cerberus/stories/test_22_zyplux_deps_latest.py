from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import Status
    from seam_fixtures import FakeRegistry, RunCheckOnDisk


CHECK_ID = "zyplux_deps_latest"

NPM_UTIL_LOCK = "packages:\n  '@zyplux/util@0.2.0':\n    resolution: {integrity: sha512-x}\n"
NPM_WORKSPACE_LOCK = (
    "importers:\n"
    "  packages/util-ts:\n"
    "    dependencies:\n"
    "      '@zyplux/tsconfig':\n"
    "        specifier: workspace:*\n"
    "        version: link:../tsconfig\n"
)
UV_CERBERUS_LOCK = """
version = 1

[[package]]
name = "zyplux-cerberus"
version = "0.6.0"
source = { registry = "https://pypi.org/simple" }
"""
UV_WORKSPACE_LOCK = """
version = 1

[[package]]
name = "zyplux"
version = "0"
source = { virtual = "." }

[[package]]
name = "zyplux-cerberus"
version = "0.6.0"
source = { editable = "apps/cerberus" }
"""
CI_IMAGE_WORKFLOW = """
jobs:
  ci:
    container: ghcr.io/zyplux/ci:0.1.0
"""


def test_22_1_1_passes_a_repo_that_uses_no_zyplux_published_artifacts(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, status: type[Status]
) -> None:
    files = {
        "pnpm-lock.yaml": "packages:\n  typescript@5.9.2:\n    resolution: {integrity: sha512-x}\n",
        "justfile": "default:\n    @just --list\n",
        ".github/workflows/ci.yml": "jobs:\n  ci:\n    container: ghcr.io/other-org/ci:1.0.0\n",
    }
    result = run_check_on_disk(CHECK_ID, files)
    assert (result.status, result.problems, fake_registry.requests) == (status.PASS, [], [])


def test_22_1_2_ignores_workspace_local_zyplux_packages(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, status: type[Status]
) -> None:
    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": NPM_WORKSPACE_LOCK, "uv.lock": UV_WORKSPACE_LOCK})
    assert (result.status, result.problems, fake_registry.requests) == (status.PASS, [], [])


def test_22_1_3_queries_each_artifact_once_per_run(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, status: type[Status]
) -> None:
    fake_registry.serve_ghcr("zyplux/ci", ["0.1.0", "latest"])
    files = {
        ".github/workflows/ci.yml": CI_IMAGE_WORKFLOW,
        ".github/workflows/nightly.yml": CI_IMAGE_WORKFLOW,
        "justfile": "smoke:\n    docker run ghcr.io/zyplux/ci:0.1.0\n",
    }
    result = run_check_on_disk(CHECK_ID, files)
    assert (result.status, result.problems) == (status.PASS, [])
    assert fake_registry.requests == [
        ("ghcr.io", "/token?service=ghcr.io&scope=repository:zyplux/ci:pull"),
        ("ghcr.io", "/v2/zyplux/ci/tags/list"),
    ]


def test_22_2_1_passes_when_the_locked_npm_version_is_the_latest(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, status: type[Status]
) -> None:
    fake_registry.serve_npm("@zyplux/util", "0.2.0")
    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": NPM_UTIL_LOCK})
    assert (result.status, result.problems) == (status.PASS, [])


def test_22_2_2_fails_naming_the_package_versions_and_location_when_the_lock_lags(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, status: type[Status]
) -> None:
    fake_registry.serve_npm("@zyplux/util", "0.3.1")
    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": NPM_UTIL_LOCK})
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        ["`@zyplux/util` is 0.2.0 in pnpm-lock.yaml, latest is 0.3.1; run `just upgrade`"],
    )


@pytest.mark.parametrize("registry_alias", ["gh", "npmjs"])
def test_22_2_3_checks_registry_qualified_pnpm_versions(
    run_check_on_disk: RunCheckOnDisk,
    fake_registry: FakeRegistry,
    monkeypatch: pytest.MonkeyPatch,
    registry_alias: str,
    status: type[Status],
) -> None:
    host = "npm.pkg.github.com" if registry_alias == "gh" else "registry.npmjs.org"
    fake_registry.serve_npm("@zyplux/util", "0.2.0", host=host)
    monkeypatch.setenv("NODE_AUTH_TOKEN", "package-read-token")
    lock = NPM_UTIL_LOCK.replace("@0.2.0", f"@{registry_alias}:0.2.0")

    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": lock})

    assert (result.status, result.problems) == (status.PASS, [])
    assert fake_registry.requests == [(host, "/@zyplux%2Futil")]


def test_22_2_4_reports_an_outdated_private_github_package(
    run_check_on_disk: RunCheckOnDisk,
    fake_registry: FakeRegistry,
    monkeypatch: pytest.MonkeyPatch,
    status: type[Status],
) -> None:
    fake_registry.serve_npm("@zyplux/util", "0.3.0", host="npm.pkg.github.com")
    monkeypatch.setenv("NODE_AUTH_TOKEN", "package-read-token")
    lock = NPM_UTIL_LOCK.replace("@0.2.0", "@gh:0.2.0")

    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": lock})

    assert (result.status, [finding.message for finding in result.problems]) == (
        status.FAIL,
        ["`@zyplux/util` is 0.2.0 in pnpm-lock.yaml, latest is 0.3.0; run `just upgrade`"],
    )


def test_22_3_1_fails_when_uv_lock_resolves_an_outdated_zyplux_distribution(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, status: type[Status]
) -> None:
    fake_registry.serve_pypi("zyplux-cerberus", "0.7.0")
    result = run_check_on_disk(CHECK_ID, {"uv.lock": UV_CERBERUS_LOCK})
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        ["`zyplux-cerberus` is 0.6.0 in uv.lock, latest is 0.7.0; run `just upgrade`"],
    )


def test_22_3_2_fails_a_version_pinned_uvx_run_but_passes_an_unpinned_one(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, status: type[Status]
) -> None:
    fake_registry.serve_pypi("zyplux-cerberus", "0.7.0")
    justfile = "lint:\n    uvx --from zyplux-cerberus==0.6.0 cerberus\n"
    workflow = "jobs:\n  ci:\n    steps:\n      - run: uvx --from zyplux-cerberus cerberus\n"
    result = run_check_on_disk(CHECK_ID, {"justfile": justfile, ".github/workflows/ci.yml": workflow})
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        ["`zyplux-cerberus` is 0.6.0 in justfile, latest is 0.7.0; run `just upgrade`"],
    )


def test_22_4_1_fails_when_a_workflow_pins_an_outdated_ghcr_image_tag(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, status: type[Status]
) -> None:
    fake_registry.serve_ghcr("zyplux/ci", ["0.1.0", "0.1.1", "latest"])
    result = run_check_on_disk(CHECK_ID, {".github/workflows/ci.yml": CI_IMAGE_WORKFLOW})
    assert (result.status, [f.message for f in result.problems]) == (
        status.FAIL,
        ["`ghcr.io/zyplux/ci` is 0.1.0 in .github/workflows/ci.yml, latest is 0.1.1; run `just upgrade`"],
    )


def test_22_4_2_passes_the_floating_latest_tag(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, status: type[Status]
) -> None:
    workflow = "jobs:\n  ci:\n    container: ghcr.io/zyplux/ci:latest\n"
    result = run_check_on_disk(CHECK_ID, {".github/workflows/ci.yml": workflow})
    assert (result.status, result.problems, fake_registry.requests) == (status.PASS, [], [])


def break_token_endpoint(_registry: FakeRegistry) -> str:
    return "https://ghcr.io/token?service=ghcr.io&scope=repository:zyplux/ci:pull: connection refused"


def break_token_payload(registry: FakeRegistry) -> str:
    registry.payloads["ghcr.io", "/token?service=ghcr.io&scope=repository:zyplux/ci:pull"] = {"detail": "denied"}
    return "zyplux/ci: response carries no `token`"


def break_tag_list_shape(registry: FakeRegistry) -> str:
    registry.serve_ghcr("zyplux/ci", [])
    registry.payloads["ghcr.io", "/v2/zyplux/ci/tags/list"] = {"tags": "0.1.0"}
    return "zyplux/ci: tag list is not a list"


def break_version_tags(registry: FakeRegistry) -> str:
    registry.serve_ghcr("zyplux/ci", ["latest", "sha-abc123"])
    return "zyplux/ci: no version tags published"


@pytest.mark.parametrize(
    "break_registry",
    [break_token_endpoint, break_token_payload, break_tag_list_shape, break_version_tags],
    ids=lambda scenario: scenario.__name__,
)
def test_22_5_1_errors_instead_of_passing_when_a_registry_lookup_fails(
    run_check_on_disk: RunCheckOnDisk,
    fake_registry: FakeRegistry,
    break_registry: Callable[[FakeRegistry], str],
    status: type[Status],
) -> None:
    failure = break_registry(fake_registry)
    files = {".github/workflows/ci.yml": CI_IMAGE_WORKFLOW, ".github/workflows/nightly.yml": CI_IMAGE_WORKFLOW}
    result = run_check_on_disk(CHECK_ID, files)
    assert result.status is status.ERROR
    assert [f.message for f in result.problems] == [f"could not determine the latest `ghcr.io/zyplux/ci`: {failure}"]


def test_22_5_2_reads_private_ghcr_images_with_the_workflow_credential(
    run_check_on_disk: RunCheckOnDisk,
    fake_registry: FakeRegistry,
    monkeypatch: pytest.MonkeyPatch,
    status: type[Status],
) -> None:
    monkeypatch.setenv("GH_TOKEN", "read-token")
    monkeypatch.setenv("GITHUB_ACTOR", "bot")
    fake_registry.serve_ghcr("zyplux/ci", ["0.1.0"])
    result = run_check_on_disk(CHECK_ID, {".github/workflows/ci.yml": CI_IMAGE_WORKFLOW})
    assert result.status is status.PASS
    assert fake_registry.request_headers == [
        {"Authorization": "Basic Ym90OnJlYWQtdG9rZW4="},
        {"Authorization": "Bearer anonymous"},
    ]
