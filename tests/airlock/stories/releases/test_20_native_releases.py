from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from cli_fixture import Reply, Response
from release_fixture import PUBLISHED_RELEASE

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def test_20_1_1_repairs_missing_github_releases_without_republishing_existing_versions(release: ReleaseFixture) -> None:
    release.published(npm=True)
    release.publish("util-v1.2.3")
    assert not release.matching("pnpm pack|pnpm publish")
    release.expect_release("util-v1.2.3")


def test_20_1_2_propagates_publication_failure_and_permits_a_successful_retry(release: ReleaseFixture) -> None:
    release.on("pnpm publish", Reply(exit_code=1))
    release.publish("util-v1.2.3", error="command failed")
    assert not release.matching("gh release create")
    release.stage_npm()
    release.publish("util-v1.2.3")
    assert release.matching("gh release create util-v1.2.3")


@pytest.mark.parametrize(
    ("override", "reason"),
    [({"name": "@zyplux/renamed"}, "workspace package name"), ({"private": True}, "private workspace packages")],
)
def test_20_1_3_rejects_mismatched_or_private_workspace_targets_before_publishing(
    release: ReleaseFixture, override: dict[str, object], reason: str
) -> None:
    release.write_json("packages/util/package.json", {"name": "@zyplux/util", "version": "1.2.3", **override})
    release.publish("util-v1.2.3", error=reason)
    assert not release.matching("pnpm publish|gh release")


def test_20_1_4_rejects_targets_excluded_from_the_workspace_before_publishing(release: ReleaseFixture) -> None:
    release.on("pnpm list", "[]")
    release.publish("util-v1.2.3", error="is not a pnpm workspace package")
    assert not release.matching("pnpm publish|gh release")


def test_20_1_5_requires_the_requested_version_in_the_registry_before_creating_a_github_release(
    release: ReleaseFixture,
) -> None:
    release.on("pnpm publish")
    release.publish("util-v1.2.3", error="npm dependencies did not become available: @zyplux/util@1.2.3")
    assert release.matching("pnpm publish")
    assert not release.matching("gh release")


def test_20_2_1_writes_pending_matrices_to_github_outputs(release: ReleaseFixture) -> None:
    release.all_published(pypi=False)
    release.env["GITHUB_OUTPUT"] = str(release.root / "outputs")
    batches = release.plan()
    assert batches == [
        {
            "environment": "pypi",
            "id": "pypi-cerberus",
            "kind": "pypi",
            "runner": "ubuntu-latest",
            "tags": ["cerberus-v2.3.4"],
        }
    ]
    assert (
        release.read("outputs") == f"matrix={json.dumps({'include': batches}, separators=(',', ':'))}\npending=true\n"
    )


@pytest.mark.parametrize(
    ("files", "should_publish"),
    [([], True), (["bdist_wheel"], True), (["sdist"], True), (["bdist_wheel", "sdist"], False)],
)
def test_20_2_2_keeps_incomplete_pypi_releases_pending_even_when_their_github_release_exists(
    release: ReleaseFixture, files: list[str], *, should_publish: bool
) -> None:
    release.serve("https://pypi.org/", Response({"urls": [{"packagetype": kind} for kind in files]}))
    release.on("gh api graphql", PUBLISHED_RELEASE)
    release.env["GITHUB_OUTPUT"] = str(release.root / "outputs")
    batches = release.plan("cerberus-v2.3.4")
    assert bool(batches) == should_publish
    assert release.read("outputs").endswith(f"pending={str(should_publish).lower()}\n")


def test_20_4_1_retries_a_partial_upload_before_creating_its_github_release(release: ReleaseFixture) -> None:
    release.serve("https://pypi.org/", Response({"urls": [{"packagetype": "bdist_wheel"}]}))
    release.on("uv build")
    release.on("uv publish", Reply(stdout="Upload interrupted.", exit_code=1))
    release.publish("cerberus-v2.3.4", error="command failed")
    assert not release.matching("gh release create")
    release.on("uv publish")
    release.publish("cerberus-v2.3.4")
    publication_attempts = 2
    assert len(release.matching("uv publish")) == publication_attempts
    assert release.matching("gh release create cerberus-v2.3.4")


@pytest.mark.parametrize(("metadata", "status"), [({}, 200), ({"urls": [{}]}, 200), ({}, 403), ({}, 502)])
def test_20_4_2_stops_before_building_or_creating_a_release_when_pypi_metadata_is_invalid(
    release: ReleaseFixture, metadata: dict[str, object], status: int
) -> None:
    release.serve("https://pypi.org/", Response(metadata, status))
    release.publish("cerberus-v2.3.4", error="")
    assert not release.matching("uv|gh release create")
