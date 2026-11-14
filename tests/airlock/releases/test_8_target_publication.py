from __future__ import annotations

import itertools
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from cli_fixture import Reply, Response
from release_fixture import MISSING_RELEASE, prepare_publication

pytestmark = pytest.mark.usefixtures("prepared_release")

if TYPE_CHECKING:
    from release_fixture import ContainerPublication, ReleaseFixture


def test_8_1_1_logs_and_does_nothing_when_the_tags_version_is_already_published(release: ReleaseFixture) -> None:
    release.all_published()
    assert "already published; nothing to do" in release.publish("util-v1.2.3").stdout
    assert not release.matching("pnpm pack|podman|uv build")


def test_8_2_1_publishes_an_npm_target_with_native_packing_and_availability_waiting(release: ReleaseFixture) -> None:
    release.stage_npm()
    release.publish("util-v1.2.3")
    release.expect_npm()


@pytest.mark.parametrize(
    "files", [None, [], ["bdist_wheel"], ["sdist"], ["bdist_wheel", "bdist_wheel"], ["bdist_wheel", "sdist"]]
)
def test_8_2_2_builds_and_publishes_incomplete_pypi_releases_using_isolated_artifacts(
    release: ReleaseFixture, files: list[str] | None
) -> None:
    release.serve(
        "https://pypi.org/",
        Response(
            {"urls": [{"packagetype": kind} for kind in files]} if files is not None else None,
            404 if files is None else 200,
        ),
    )
    release.on("uv publish")
    release.publish("cerberus-v2.3.4")
    build = release.matching("uv build")[0]
    assert build.argv[:3] == ["build", "--package", "zyplux-cerberus"]
    assert build.argv[3] == "--out-dir"
    assert not Path(build.argv[-1]).exists()
    if files == ["bdist_wheel", "sdist"]:
        assert not release.matching("uv publish")
    else:
        assert release.matching("uv publish")[0].argv == [
            "publish",
            "--check-url",
            "https://pypi.org/simple/",
            str(Path(build.argv[-1]) / "*"),
        ]


def test_8_2_3_requires_gh_token_before_pushing_a_ghcr_target(release: ReleaseFixture) -> None:
    release.container()
    release.env["GH_TOKEN"] = ""
    release.publish("ci-image-v3.4.5", error="GH_TOKEN is required to push to GHCR")
    assert not release.matching("podman")


def test_8_2_4_requires_github_actor_before_pushing_a_ghcr_target(release: ReleaseFixture) -> None:
    release.container()
    release.env["GITHUB_ACTOR"] = ""
    release.publish("ci-image-v3.4.5", error="GITHUB_ACTOR is required to push to GHCR")
    assert not release.matching("podman")


def test_8_2_5_publishes_a_versioned_ghcr_image_and_its_release_manifest(
    release: ReleaseFixture, container: ContainerPublication
) -> None:
    release.env.update(GH_TOKEN=release.credential, GITHUB_ACTOR="zyplux-bot")
    release.publish(container.batch["tags"][0])
    login = release.matching("podman login")[0]
    assert login.argv == ["login", "ghcr.io", "-u", "zyplux-bot", "--password-stdin"]
    assert login.stdin == release.credential
    assert [call.argv[0] for call in release.matching("podman")] == ["login", "build", "push", "logout"]
    assert "--label org.opencontainers.image.revision=reviewed-sha" in release.matching("podman build")[0].text


def test_8_2_6_propagates_native_npm_publication_failures(release: ReleaseFixture) -> None:
    release.stage_npm(exit_code=1)
    release.publish("util-v1.2.3", error="command failed with exit code 1")
    release.expect_npm()


@pytest.mark.parametrize(
    ("command", "should_logout"), [("podman login", False), ("podman build", True), ("podman push", True)]
)
def test_8_2_7_removes_ghcr_credentials_after_a_successful_login_when_publication_fails(
    release: ReleaseFixture, command: str, *, should_logout: bool
) -> None:
    release.container()
    release.on(command, Reply(exit_code=1))
    release.publish("ci-image-v3.4.5", error="command failed with exit code 1")
    assert bool(release.matching("podman logout")) == should_logout


def test_8_3_1_authenticates_the_configured_registry_and_lets_pnpm_apply_publishconfig(release: ReleaseFixture) -> None:
    release.write_json(
        "packages/util/package.json",
        {
            "name": "@zyplux/util",
            "version": "1.2.3",
            "publishConfig": {"access": "restricted", "registry": "https://npm.pkg.github.com"},
        },
    )
    release.env["NODE_AUTH_TOKEN"] = release.credential
    release.stage_npm()
    release.publish("util-v1.2.3")
    request = next(
        request for request in release.requests if request.url == "https://npm.pkg.github.com/%40zyplux%2Futil"
    )
    assert request.method == "GET"
    assert request.headers["authorization"] == f"Bearer {release.credential}"
    release.expect_npm()


def test_8_3_2_rejects_missing_credentials_before_checking_a_private_registry(release: ReleaseFixture) -> None:
    release.write_json(
        "packages/util/package.json",
        {"name": "@zyplux/util", "version": "1.2.3", "publishConfig": {"registry": "https://npm.pkg.github.com"}},
    )
    release.publish("util-v1.2.3", error="GitHub Packages requires authentication")
    assert not release.requests


@pytest.mark.parametrize(
    ("registry", "status"),
    list(itertools.product(["https://registry.npmjs.org", "https://npm.pkg.github.com"], [403, 502])),
)
def test_8_3_3_rejects_registry_failures_without_attempting_publication(
    release: ReleaseFixture, registry: str, status: int
) -> None:
    release.write_json(
        "packages/util/package.json",
        {"name": "@zyplux/util", "version": "1.2.3", "publishConfig": {"registry": registry}},
    )
    release.env["NODE_AUTH_TOKEN"] = release.credential
    release.serve(registry, Response(status=status))
    release.publish("util-v1.2.3", error=f"failed: {status}")
    assert not release.matching("pnpm pack|pnpm publish")


def test_8_3_4_rejects_unsupported_registry_destinations_before_making_a_request(release: ReleaseFixture) -> None:
    release.write_json(
        "packages/util/package.json",
        {"name": "@zyplux/util", "version": "1.2.3", "publishConfig": {"registry": "https://example.com"}},
    )
    release.publish("util-v1.2.3", error="")
    assert not release.requests


@pytest.mark.parametrize("registry", ["https://registry.npmjs.org/", "https://npm.pkg.github.com/"])
def test_8_3_5_accepts_supported_registry_urls_with_a_trailing_slash(release: ReleaseFixture, registry: str) -> None:
    release.write_json(
        "packages/util/package.json",
        {"name": "@zyplux/util", "version": "1.2.3", "publishConfig": {"registry": registry}},
    )
    prepare_publication(release)
    release.env["NODE_AUTH_TOKEN"] = release.credential
    release.serve(
        registry, Response({"versions": {"1.2.3": {"dist": {"tarball": "https://registry.npmjs.org/util.tgz"}}}})
    )
    assert "already published; nothing to do" in release.publish("util-v1.2.3").stdout
    assert {request.url for request in release.requests} == {
        f"{registry}%40zyplux%2Futil",
        "https://registry.npmjs.org/util.tgz",
    }
    assert not release.matching("pnpm publish")
    assert len(release.matching("pnpm pack")) == 1


@pytest.mark.parametrize("registry", [None, "https://registry.npmjs.org"])
def test_8_3_6_prefers_the_package_scopes_registry_setting(release: ReleaseFixture, registry: str | None) -> None:
    config = {"@zyplux:registry": "https://npm.pkg.github.com/"}
    if registry:
        config["registry"] = registry
    release.write_json(
        "packages/util/package.json", {"name": "@zyplux/util", "version": "1.2.3", "publishConfig": config}
    )
    prepare_publication(release)
    release.env["NODE_AUTH_TOKEN"] = release.credential
    release.serve(
        "https://npm.pkg.github.com/",
        Response({"versions": {"1.2.3": {"dist": {"tarball": "https://registry.npmjs.org/util.tgz"}}}}),
    )
    assert "already published; nothing to do" in release.publish("util-v1.2.3").stdout
    assert {request.url for request in release.requests} == {
        "https://npm.pkg.github.com/%40zyplux%2Futil",
        "https://registry.npmjs.org/util.tgz",
    }
    assert not release.matching("pnpm publish")
    assert len(release.matching("pnpm pack")) == 1


@pytest.mark.parametrize(
    ("registry", "is_published"),
    list(itertools.product(["https://registry.npmjs.org", "https://npm.pkg.github.com"], [False, True])),
)
def test_8_3_7_checks_the_requested_version_in_registry_package_metadata(
    release: ReleaseFixture, registry: str, *, is_published: bool
) -> None:
    release.write_json(
        "packages/util/package.json",
        {"name": "@zyplux/util", "version": "1.2.3", "publishConfig": {"registry": registry}},
    )
    release.env["NODE_AUTH_TOKEN"] = release.credential
    versions: dict[str, dict[str, object]] = {"1.2.2": {}}
    if is_published:
        versions["1.2.3"] = {"dist": {"tarball": "https://registry.npmjs.org/util.tgz"}}
    release.serve(registry, Response(status=502))
    release.serve(f"{registry}/%40zyplux%2Futil", Response({"versions": versions}))
    release.serve("https://registry.npmjs.org/util.tgz", Response())
    release.stage_npm()
    execution = release.publish("util-v1.2.3")
    assert f"{registry}/%40zyplux%2Futil" in [request.url for request in release.requests]
    if is_published:
        assert "already published; nothing to do" in execution.stdout
        assert not release.matching("pnpm publish")
        assert len(release.matching("pnpm pack")) == 1
    else:
        release.expect_npm()


def test_8_3_8_rejects_malformed_package_metadata_without_attempting_publication(release: ReleaseFixture) -> None:
    release.write_json(
        "packages/util/package.json",
        {"name": "@zyplux/util", "version": "1.2.3", "publishConfig": {"registry": "https://npm.pkg.github.com"}},
    )
    release.env["NODE_AUTH_TOKEN"] = release.credential
    release.serve("https://npm.pkg.github.com/", Response({}))
    release.publish("util-v1.2.3", error="")
    assert not release.matching("pnpm pack|pnpm publish")


@pytest.mark.parametrize(("artifact", "github_release"), list(itertools.product([False, True], repeat=2)))
def test_8_4_1_publishes_only_missing_artifacts_and_creates_only_missing_github_releases_at_head(
    release: ReleaseFixture, *, artifact: bool, github_release: bool
) -> None:
    release.published(npm=artifact)
    release.on("git rev-parse HEAD", "reviewed-sha")
    release.on(
        "gh api graphql",
        '{"data":{"repository":{"release":{"id":"release-id"}}}}' if github_release else MISSING_RELEASE,
    )
    release.stage_npm()
    release.publish("util-v1.2.3")
    if artifact:
        assert not release.matching("pnpm publish")
        expected_packs = 0 if github_release else 1
        assert len(release.matching("pnpm pack")) == expected_packs
    else:
        release.expect_npm()
    if github_release:
        assert not release.matching("gh release create")
    else:
        release.expect_release("util-v1.2.3", "reviewed-sha")


def test_8_4_2_leaves_github_release_metadata_unpublished_when_the_registry_rejects_publication(
    release: ReleaseFixture,
) -> None:
    release.stage_npm(exit_code=1)
    release.publish("util-v1.2.3", error="command failed with exit code 1")
    assert not release.matching("gh api graphql|gh release create")


def test_8_4_3_rebuilds_incomplete_ghcr_releases_from_a_pushed_digest(
    release: ReleaseFixture, container: ContainerPublication
) -> None:
    release.published(ghcr=True)
    release.publish(container.batch["tags"][0])
    assert release.matching("podman build")
    assert release.matching("podman push --digestfile")
    assert release.matching("gh release upload ci-image-v3.4.5")
