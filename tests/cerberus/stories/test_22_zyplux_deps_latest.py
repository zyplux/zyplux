from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import Status
    from seam_fixtures import FakeProc, FakeRegistry, RunCheckOnDisk


CHECK_ID = "zyplux_deps_latest"

NPM_UTIL_LOCK = "packages:\n  '@zyplux/util@0.2.0':\n    resolution: {integrity: sha512-x}\n"
PNPM_TOOLCHAIN_LOCK = """lockfileVersion: '9.0'
importers:
  .:
    packageManagerDependencies:
      pnpm:
        specifier: 12.14.0
        version: 12.14.0
packages:
  pnpm@12.14.0:
    resolution: {integrity: sha512-pnpm}
snapshots:
  pnpm@12.14.0: {}
---
"""
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


@pytest.mark.parametrize("lock_prefix", ["", PNPM_TOOLCHAIN_LOCK], ids=["single-document", "toolchain-and-workspace"])
def test_22_1_2_ignores_workspace_local_zyplux_packages(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, lock_prefix: str, status: type[Status]
) -> None:
    result = run_check_on_disk(
        CHECK_ID, {"pnpm-lock.yaml": lock_prefix + NPM_WORKSPACE_LOCK, "uv.lock": UV_WORKSPACE_LOCK}
    )
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


@pytest.mark.parametrize("lock_prefix", ["", PNPM_TOOLCHAIN_LOCK], ids=["single-document", "toolchain-and-workspace"])
def test_22_2_1_passes_when_the_locked_npm_version_is_the_latest(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, lock_prefix: str, status: type[Status]
) -> None:
    fake_registry.serve_npm("@zyplux/util", "0.2.0")
    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": lock_prefix + NPM_UTIL_LOCK})
    assert (result.status, result.problems) == (status.PASS, [])
    assert fake_registry.requests == [("registry.npmjs.org", "/%40zyplux%2Futil")]


@pytest.mark.parametrize("lock_prefix", ["", PNPM_TOOLCHAIN_LOCK], ids=["single-document", "toolchain-and-workspace"])
def test_22_2_2_fails_naming_the_package_versions_and_location_when_the_lock_lags(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, lock_prefix: str, status: type[Status]
) -> None:
    fake_registry.serve_npm("@zyplux/util", "0.3.1")
    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": lock_prefix + NPM_UTIL_LOCK})
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
    lock = PNPM_TOOLCHAIN_LOCK + NPM_UTIL_LOCK.replace("@0.2.0", f"@{registry_alias}:0.2.0")

    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": lock})

    assert (result.status, result.problems) == (status.PASS, [])
    assert fake_registry.requests == [(host, "/%40zyplux%2Futil")]


@pytest.mark.parametrize("lock_prefix", ["", PNPM_TOOLCHAIN_LOCK], ids=["single-document", "toolchain-and-workspace"])
def test_22_2_4_reports_an_outdated_private_github_package(
    run_check_on_disk: RunCheckOnDisk,
    fake_registry: FakeRegistry,
    monkeypatch: pytest.MonkeyPatch,
    lock_prefix: str,
    status: type[Status],
) -> None:
    fake_registry.serve_npm("@zyplux/util", "0.3.0", host="npm.pkg.github.com")
    monkeypatch.setenv("NODE_AUTH_TOKEN", "package-read-token")
    lock = lock_prefix + NPM_UTIL_LOCK.replace("@0.2.0", "@gh:0.2.0")

    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": lock})

    assert (result.status, [finding.message for finding in result.problems]) == (
        status.FAIL,
        ["`@zyplux/util` is 0.2.0 in pnpm-lock.yaml, latest is 0.3.0; run `just upgrade`"],
    )


@pytest.mark.parametrize(
    "lock_prefix",
    ["", PNPM_TOOLCHAIN_LOCK + NPM_UTIL_LOCK + "\n---\n"],
    ids=["first-document", "after-valid-documents"],
)
def test_22_2_5_reports_malformed_lockfiles_without_registry_lookups(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, lock_prefix: str, status: type[Status]
) -> None:
    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": lock_prefix + "packages: ["})

    assert result.status is status.ERROR
    assert len(result.problems) == 1
    assert "could not parse pnpm-lock.yaml:" in result.problems[0].message
    assert fake_registry.requests == []


def test_22_2_6_checks_packages_in_each_document(
    run_check_on_disk: RunCheckOnDisk, fake_registry: FakeRegistry, status: type[Status]
) -> None:
    fake_registry.serve_npm("@zyplux/util", "0.3.0")
    fake_registry.serve_npm("@zyplux/cz", "0.2.0")
    lock = NPM_UTIL_LOCK + "---\n" + NPM_UTIL_LOCK.replace("@zyplux/util", "@zyplux/cz")

    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": lock})

    assert (result.status, [finding.message for finding in result.problems]) == (
        status.FAIL,
        ["`@zyplux/util` is 0.2.0 in pnpm-lock.yaml, latest is 0.3.0; run `just upgrade`"],
    )
    assert sorted(fake_registry.requests) == [
        ("registry.npmjs.org", "/%40zyplux%2Fcz"),
        ("registry.npmjs.org", "/%40zyplux%2Futil"),
    ]


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
    fake_registry.serve_ghcr("zyplux/ci", ["0.1.0", "0.1.1", "0.2.0-beta.1", "latest", "sha-abc123"])
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
    return "token"


def break_tag_list_shape(registry: FakeRegistry) -> str:
    registry.serve_ghcr("zyplux/ci", [])
    registry.payloads["ghcr.io", "/v2/zyplux/ci/tags/list"] = {"tags": "0.1.0"}
    return "tags"


def break_version_tags(registry: FakeRegistry) -> str:
    registry.serve_ghcr("zyplux/ci", ["latest", "sha-abc123"])
    return "zyplux/ci: no published versions"


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
    assert len(result.problems) == 1
    assert result.problems[0].message.startswith("could not determine the latest `ghcr.io/zyplux/ci`: ")
    assert failure in result.problems[0].message


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
    assert [headers["authorization"] for headers in fake_registry.request_headers] == [
        "Basic Ym90OnJlYWQtdG9rZW4=",
        "Bearer anonymous",
    ]


@pytest.mark.parametrize("source", ["GH_TOKEN", "GITHUB_TOKEN", "gh login"])
def test_22_6_1_reads_private_npm_metadata_with_existing_github_credentials(
    run_check_on_disk: RunCheckOnDisk,
    fake_registry: FakeRegistry,
    fake_proc: FakeProc,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    if source == "gh login":
        fake_proc.serve("gh auth", stdout="saved-token\n")
    else:
        monkeypatch.setenv(source, "saved-token")
    fake_registry.serve_npm("@zyplux/util", "0.2.0", host="npm.pkg.github.com")
    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": NPM_UTIL_LOCK.replace("@0.2.0", "@gh:0.2.0")})
    assert result.problems == []
    assert [headers["authorization"] for headers in fake_registry.request_headers] == ["Bearer saved-token"]
    if source != "gh login":
        assert fake_proc.calls == []


def test_22_6_2_reads_private_containers_with_the_saved_login_and_actor(
    run_check_on_disk: RunCheckOnDisk,
    fake_registry: FakeRegistry,
    fake_proc: FakeProc,
    status: type[Status],
) -> None:
    fake_proc.serve("gh auth", stdout="saved-token\n")
    fake_registry.payloads["api.github.com", "/user"] = {"login": "reader"}
    fake_registry.serve_ghcr("zyplux/ci", ["0.1.0"])
    result = run_check_on_disk(CHECK_ID, {".github/workflows/ci.yml": CI_IMAGE_WORKFLOW})
    assert (result.status, result.problems) == (status.PASS, [])
    assert [headers["authorization"] for headers in fake_registry.request_headers[:2]] == [
        "Bearer saved-token",
        "Basic cmVhZGVyOnNhdmVkLXRva2Vu",
    ]
    assert fake_registry.request_headers[0]["user-agent"] == "zyplux-airlock"


def test_22_6_3_reports_missing_private_registry_credentials(
    run_check_on_disk: RunCheckOnDisk,
    fake_registry: FakeRegistry,
    status: type[Status],
) -> None:
    result = run_check_on_disk(CHECK_ID, {"pnpm-lock.yaml": NPM_UTIL_LOCK.replace("@0.2.0", "@gh:0.2.0")})
    assert result.status == status.ERROR
    assert "gh auth login --scopes read:packages" in result.problems[0].message
    assert fake_registry.requests == []
