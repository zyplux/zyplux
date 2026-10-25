from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from cli_fixture import Reply, Response
from release_fixture import PUBLISHED_RELEASE

if TYPE_CHECKING:
    from release_fixture import ContainerPublication, ReleaseFixture


def test_22_1_1_builds_from_the_declared_dockerfile_and_context_and_uploads_a_digest_pinned_manifest(
    release: ReleaseFixture, container: ContainerPublication
) -> None:
    release.configure("ghcr", 'dockerfile = "containers/ci/Containerfile"\nbuild_context = "."')
    release.publish_batch(container.batch)
    assert json.loads(container.manifest) == {"image": f"ghcr.io/zyplux/ci@sha256:{'1' * 64}", "version": "3.4.5"}
    assert release.matching("podman build")[0].argv == [
        "build",
        "--file",
        str(release.root / "containers/ci/Containerfile"),
        "--label",
        "org.opencontainers.image.version=3.4.5",
        "--label",
        "org.opencontainers.image.revision=reviewed-sha",
        "-t",
        "ghcr.io/zyplux/ci:3.4.5",
        str(release.root),
    ]
    assert release.matching("podman push")[0].argv[0:2] == ["push", "--digestfile"]
    assert [call.argv[1] for call in release.matching("gh release")] == ["create", "upload", "edit"]
    assert release.matching("podman logout ghcr.io")


def test_22_1_2_rebuilds_unfinished_releases_despite_an_existing_image_tag(
    release: ReleaseFixture, container: ContainerPublication
) -> None:
    release.on("gh api graphql", '{"data":{"repository":{"release":{"isDraft":true,"releaseAssets":{"nodes":[]}}}}}')
    release.publish_batch(container.batch)
    release.published(ghcr=True)
    release.on("git rev-parse HEAD", "retry-sha")
    release.publish_batch(container.batch)
    assert f"sha256:{'2' * 64}" in container.manifest
    build_attempts = 2
    assert len(release.matching("podman build")) == build_attempts
    assert "org.opencontainers.image.revision=retry-sha" in release.matching("podman build")[-1].text


@pytest.mark.parametrize(
    ("command", "reply", "reason"),
    [
        ("podman build", Reply(exit_code=1), "command failed"),
        ("podman push", Reply(exit_code=1), "command failed"),
        ("podman push", "", "ENOENT"),
    ],
)
def test_22_1_3_keeps_releases_unpublished_and_removes_credentials_when_image_publication_fails(
    release: ReleaseFixture, container: ContainerPublication, command: str, reply: Reply | str, reason: str
) -> None:
    release.on(command, reply)
    release.publish_batch(container.batch, error=reason)
    assert not release.matching("gh release")
    assert release.matching("podman logout ghcr.io")


def test_22_1_4_preserves_a_finalized_release_and_its_manifest(
    release: ReleaseFixture, container: ContainerPublication
) -> None:
    release.published(ghcr=True)
    release.on("gh api graphql", PUBLISHED_RELEASE)
    release.publish_batch(container.batch)
    assert not release.matching("podman|gh release (create|upload|edit)")


def test_22_1_5_rejects_a_finalized_release_whose_image_is_missing_without_changing_its_manifest(
    release: ReleaseFixture, container: ContainerPublication
) -> None:
    release.published(ghcr=True)
    release.serve(f"https://ghcr.io/v2/zyplux/ci/manifests/sha256:{'1' * 64}", Response(status=404))
    release.on("gh api graphql", PUBLISHED_RELEASE)
    release.plan("ci-image-v3.4.5", error="is missing image")
    release.publish_batch(container.batch, error="published release ci-image-v3.4.5 is missing image")
    assert not release.matching("podman|gh release (create|upload|edit)")


def test_22_1_6_requires_the_pushed_image_in_the_registry_before_creating_its_release(
    release: ReleaseFixture, container: ContainerPublication
) -> None:
    container.is_published = False
    release.publish_batch(container.batch, error="container push did not publish image ghcr.io/zyplux/ci:3.4.5")
    assert not release.matching("gh release")
    assert release.matching("podman logout ghcr.io")


def test_22_1_7_leaves_the_release_as_a_draft_when_manifest_upload_fails(
    release: ReleaseFixture, container: ContainerPublication
) -> None:
    release.on("gh release upload", Reply(exit_code=1))
    release.publish_batch(container.batch, error="command failed")
    assert release.matching("gh release create ci-image-v3.4.5 --draft")
    assert not release.matching("gh release edit")
    assert release.matching("podman logout ghcr.io")


@pytest.mark.parametrize(
    "fields",
    [
        'build_context = "../outside"',
        'build_context = "/tmp"',
        'dockerfile = "../Dockerfile"',
        'dockerfile = "/tmp/Dockerfile"',
    ],
)
def test_22_2_1_requires_repository_relative_build_paths(
    release: ReleaseFixture, container: ContainerPublication, fields: str
) -> None:
    release.configure("ghcr", fields)
    release.publish_batch(container.batch, error="release paths must be repository-relative")
    assert not release.matching("podman")


@pytest.mark.parametrize("fields", ['artifact_command = ["custom-builder"]', 'assets = ["custom.json"]'])
def test_22_2_2_rejects_unsupported_custom_builder_declarations(release: ReleaseFixture, fields: str) -> None:
    release.configure("ghcr", fields)
    release.plan(error="Unrecognized key")


def test_22_2_4_rejects_published_container_releases_with_missing_manifests_during_planning(
    release: ReleaseFixture, container: ContainerPublication
) -> None:
    release.published(ghcr=True)
    release.on("gh api graphql", '{"data":{"repository":{"release":{"isDraft":false,"releaseAssets":{"nodes":[]}}}}}')
    release.plan(container.batch["tags"][0], error="missing required assets")
    assert not release.matching("podman")


@pytest.mark.parametrize("digest", ["", "sha256:short", f"sha512:{'1' * 64}", f"sha256:{'g' * 64}"])
def test_22_2_5_rejects_malformed_pushed_digests_before_uploading_the_manifest(
    release: ReleaseFixture, container: ContainerPublication, digest: str
) -> None:
    container.digest = digest
    release.publish_batch(container.batch, error="")
    assert not release.matching("gh release")
    assert release.matching("podman logout ghcr.io")
