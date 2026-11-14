from __future__ import annotations

import json
import re
import tomllib
from typing import TYPE_CHECKING

import pytest
from archive_fixture import stage_packagers
from cli_fixture import Reply, Response
from release_fixture import list_workspace_packages, prepare_publication

if TYPE_CHECKING:
    from cli_fixture import Command, Request
    from release_fixture import ReleaseFixture


def test_24_1_1_plans_separate_jobs_without_packing_packages_or_discovering_dependencies(
    release: ReleaseFixture,
) -> None:
    consumer = release.consumer()
    assert [batch["tags"] for batch in release.plan() if batch["kind"] == "npm"] == [
        [consumer.tag],
        ["independent-v1.2.3"],
        ["util-v1.2.3"],
    ]
    assert not release.matching("pnpm pack|pnpm list|tar -xOf")


@pytest.mark.parametrize(
    ("has_packing_error", "error"),
    [(True, "command failed"), (False, "npm dependencies did not become available: @zyplux/util@1.2.3")],
)
def test_24_1_2_confines_npm_publication_failures_to_their_jobs(
    release: ReleaseFixture, *, has_packing_error: bool, error: str
) -> None:
    consumer = release.consumer()
    if has_packing_error:
        release.on("pnpm pack", Reply(exit_code=1))
    batches = release.plan()
    assert not release.matching("pnpm pack")
    failed = next(batch for batch in batches if consumer.tag in batch["tags"])
    independent = next(batch for batch in batches if "independent-v1.2.3" in batch["tags"])
    release.publish_batch(failed, error=error)
    assert not release.matching("pnpm publish")
    stage_packagers(release)
    release.stage_npm()
    release.publish_batch(independent)
    assert release.matching("gh release create independent-v1.2.3")
    assert not release.matching(f"gh release create {consumer.tag}")


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"private": True}, "is private"),
        ({"version": "1.2.4"}, "configured name and version"),
        ({"path": "/unconfigured"}, "declare an npm target"),
    ],
)
def test_24_1_3_rejects_invalid_workspace_dependencies(
    release: ReleaseFixture, override: dict[str, object], reason: str
) -> None:
    consumer = release.consumer()
    batch = release.plan(consumer.tag)[0]
    packages = list_workspace_packages(release.root)
    release.on(
        "pnpm list",
        json.dumps([{**package, **override} if package["name"] == "@zyplux/util" else package for package in packages]),
    )
    release.publish_batch(batch, error=reason)
    assert not release.matching("pnpm publish")


@pytest.mark.parametrize("hook", ["prepublishOnly", "publish", "postpublish"])
def test_24_1_5_rejects_publish_only_lifecycle_hooks_before_packing(release: ReleaseFixture, hook: str) -> None:
    consumer = release.consumer()
    release.write_json(
        "packages/consumer/package.json",
        {"name": consumer.package_name, "scripts": {hook: "build-package"}, "version": consumer.version},
    )
    batch = release.plan(consumer.tag)[0]
    release.publish_batch(batch, error="publish-only hooks are unsupported")
    assert not release.matching("pnpm pack|pnpm publish")


def test_24_1_6_encodes_target_names_in_archive_filenames(release: ReleaseFixture) -> None:
    consumer = release.consumer()
    release.write(
        "airlock_targets.toml",
        release.read("airlock_targets.toml").replace("[consumer]", '["team/consumer"]'),
    )
    release.on(
        re.compile(r"^tar -xOf \S*/team%2Fconsumer-v1\.2\.3\.tgz "),
        json.dumps({"name": consumer.package_name, "version": consumer.version}),
    )
    batch = release.plan("team/consumer-v1.2.3")[0]
    release.stage_npm()
    release.publish_batch(batch)
    assert "/team%2Fconsumer-v1.2.3.tgz" in release.matching("pnpm pack")[0].text
    assert release.matching("gh release create team/consumer-v1.2.3")


@pytest.mark.parametrize("failure", [None, 408, 429, 503, "timeout"])
def test_24_2_1_waits_for_dependency_metadata_and_tarball_visibility_before_uploading(
    release: ReleaseFixture, failure: int | str | None
) -> None:
    consumer = release.consumer()
    batch = release.plan(consumer.tag)[0]
    metadata_checks = 0
    tarball_checks = 0

    def fail_request() -> Response:
        return (
            Response(error="TimeoutError")
            if failure == "timeout"
            else Response(status=failure if isinstance(failure, int) else 404)
        )

    def metadata(_: Request) -> Response:
        nonlocal metadata_checks
        metadata_checks += 1
        if metadata_checks == 1 and failure is not None:
            return fail_request()
        return Response({
            "versions": {}
            if metadata_checks == 1
            else {"1.2.3": {"dist": {"tarball": "https://registry.npmjs.org/util.tgz"}}}
        })

    def tarball(_: Request) -> Response:
        nonlocal tarball_checks
        tarball_checks += 1
        return fail_request() if tarball_checks == 1 else Response()

    def publish(_: Command) -> str:
        tarball_attempts = 2
        assert tarball_checks == tarball_attempts
        release.published(npm=True)
        return ""

    release.serve("https://registry.npmjs.org/%40zyplux%2Futil", metadata)
    release.serve("https://registry.npmjs.org/util.tgz", tarball)
    release.on("pnpm publish", publish)
    release.publish_batch(batch)
    assert release.matching(f"gh release create {consumer.tag}")
    metadata_attempts = 3
    assert metadata_checks == metadata_attempts


def test_24_2_3_propagates_registry_authorization_errors_before_uploading(release: ReleaseFixture) -> None:
    consumer = release.consumer()
    batch = release.plan(consumer.tag)[0]
    release.serve("https://registry.npmjs.org/%40zyplux%2Futil", Response(status=403))
    release.publish_batch(batch, error="403")
    assert not release.matching("pnpm publish")


def test_24_2_4_waits_for_existing_version_tarballs_before_repairing_github_releases(release: ReleaseFixture) -> None:
    consumer = release.consumer()
    batch = release.plan(consumer.tag)[0]
    release.published(npm=True)
    release.serve("https://registry.npmjs.org/util.tgz", Response(status=404))
    release.publish_batch(batch, error="npm dependencies did not become available")
    assert not release.matching("pnpm pack|pnpm publish|gh release create")


def test_24_3_1_publishes_a_bundle_after_its_packing_hook_removes_private_workspace_dependencies(
    release: ReleaseFixture,
) -> None:
    consumer = release.bundled_consumer()
    batch = release.plan(consumer.tag)[0]
    release.stage_npm()
    release.publish_batch(batch)
    release.expect_npm(consumer.dir)
    assert release.matching(f"gh release create {consumer.tag}")


@pytest.mark.parametrize(
    "dependencies",
    [{"utility": "npm:@zyplux/util@1.2.3"}, {"utility": "npm:@zyplux/util"}, {"@zyplux/util": "npm:^1.2.0"}],
)
def test_24_3_2_waits_for_the_real_package_behind_an_npm_alias(
    release: ReleaseFixture, dependencies: dict[str, str]
) -> None:
    consumer = release.consumer()
    release.on(
        "tar -xOf",
        json.dumps({"dependencies": dependencies, "name": consumer.package_name, "version": consumer.version}),
    )
    release.publish_batch(
        release.plan(consumer.tag)[0], error="npm dependencies did not become available: @zyplux/util@1.2.3"
    )
    assert not release.matching("pnpm publish")


@pytest.mark.parametrize(
    "bundling",
    [
        {"bundleDependencies": ["@zyplux/util"]},
        {"bundledDependencies": ["@zyplux/util"]},
        {"bundleDependencies": True},
        {"bundledDependencies": True},
        {"dependencies": {"@zyplux/util": "^9.0.0"}},
        {"dependencies": {"utility": "npm:@zyplux/util@^9.0.0"}},
    ],
)
def test_24_3_3_skips_workspace_waits_for_bundled_or_incompatible_dependencies(
    release: ReleaseFixture, bundling: dict[str, object]
) -> None:
    consumer = release.consumer()
    release.on(
        re.compile(r"^tar -xOf \S*/consumer-v1\.2\.3\.tgz "),
        json.dumps({
            "dependencies": {"@zyplux/util": "1.2.3"},
            "name": consumer.package_name,
            "version": consumer.version,
            **bundling,
        }),
    )
    batch = release.plan(consumer.tag)[0]
    release.stage_npm()
    release.publish_batch(batch)
    assert release.matching(f"gh release create {consumer.tag}")


@pytest.mark.parametrize("override", [{"name": "@zyplux/unexpected"}, {"version": "9.9.9"}])
def test_24_3_4_rejects_packing_hooks_that_change_the_package_identity(
    release: ReleaseFixture, override: dict[str, str]
) -> None:
    consumer = release.consumer()
    release.on("tar -xOf", json.dumps({"name": consumer.package_name, "version": consumer.version, **override}))
    release.publish_batch(release.plan(consumer.tag)[0], error="packed package identity must match")
    assert not release.matching("pnpm publish")


@pytest.mark.parametrize("has_transitive", [False, True])
def test_24_4_1_rejects_reachable_unpublished_cycles_without_packing_peers(
    release: ReleaseFixture, *, has_transitive: bool
) -> None:
    consumer = release.consumer()
    for name, dependency in (
        ("util", "independent" if has_transitive else "consumer"),
        ("independent", "consumer"),
    ):
        release.write_json(
            f"packages/{name}/package.json",
            {"name": f"@zyplux/{name}", "version": "1.2.3", "dependencies": {f"@zyplux/{dependency}": "1.2.3"}},
        )
    prepare_publication(release)
    manifest = tomllib.loads(release.read("airlock_targets.toml"))
    assert manifest["consumer"]["depends_on"] == ["util"]
    release.publish(consumer.tag, error="cyclic production workspace dependency")
    assert len(release.matching("pnpm pack")) == 1
    assert not release.matching("pnpm publish|gh release create")


def test_24_4_2_uses_prepared_packing_hook_metadata_to_break_apparent_source_cycles(release: ReleaseFixture) -> None:
    consumer = release.bundled_consumer()
    for name, dependency in (("consumer", "util"), ("util", "consumer")):
        release.write_json(
            f"packages/{name}/package.json",
            {"name": f"@zyplux/{name}", "version": "1.2.3", "dependencies": {f"@zyplux/{dependency}": "1.2.3"}},
        )
    release.write(
        ".pnpmfile.mjs",
        "export const hooks = { beforePacking(manifest) { "
        "delete manifest.dependencies?.['@zyplux/consumer']; return manifest; } };",
    )
    release.stage_npm()
    manifest = tomllib.loads(release.read("airlock_targets.toml"))
    assert "depends_on" not in manifest["util"]
    release.serve(
        "https://registry.npmjs.org/%40zyplux%2Futil",
        Response({"versions": {"1.2.3": {"dist": {"tarball": "https://registry.npmjs.org/util.tgz"}}}}),
    )
    release.publish(consumer.tag)
    release.expect_npm(consumer.dir)
    release.expect_release(consumer.tag)


@pytest.mark.parametrize("dependency", ["unknown", "cerberus"])
def test_24_4_3_rejects_invalid_prepared_peer_dependencies_without_packing_them(
    release: ReleaseFixture, dependency: str
) -> None:
    consumer = release.consumer()
    manifest = release.read("airlock_targets.toml")
    release.write(
        "airlock_targets.toml",
        manifest.replace("[util]\n", f'[util]\ndepends_on = ["{dependency}"]\n'),
    )
    release.publish(consumer.tag, error="run airlock prepare")
    assert len(release.matching("pnpm pack")) == 1
    assert not release.matching("pnpm publish|gh release create")


@pytest.mark.parametrize("declaration", ["", "depends_on = []\n"])
def test_24_4_4_accepts_omitted_or_empty_dependencies_and_omits_them_during_preparation(
    release: ReleaseFixture, declaration: str
) -> None:
    release.run("prepare")
    release.configure("npm", declaration)
    release.stage_npm()
    assert "depends_on" not in tomllib.loads(release.read("airlock_targets.toml"))["util"]
    release.configure("npm", declaration)
    release.calls.clear()
    release.publish("util-v1.2.3")
    release.expect_npm()


def test_24_4_5_rejects_omitting_a_real_dependency_before_publication(release: ReleaseFixture) -> None:
    consumer = release.consumer()
    release.write("airlock_targets.toml", release.read("airlock_targets.toml").replace('depends_on = ["util"]\n', ""))
    release.publish(consumer.tag, error="prepared dependencies differ from package contents")
    assert not release.matching("pnpm publish|gh release create")


def test_24_4_6_resolves_exact_dependency_versions_from_target_version_sources(release: ReleaseFixture) -> None:
    consumer = release.consumer()
    release.write(
        "airlock_targets.toml",
        release.read("airlock_targets.toml").replace("[util]", '[util]\nrelease_tag = "runtime"'),
    )
    release.write_json("packages/util/package.json", {"name": "@zyplux/util", "version": "1.2.4"})
    release.write("packages/util/CHANGELOG.md", "# Util\n\n## 1.2.4\n\n- Update runtime.\n")
    prepare_publication(release)
    manifest = tomllib.loads(release.read("airlock_targets.toml"))
    assert manifest["consumer"]["depends_on"] == ["util"]
    checks = []

    def metadata(request: Request) -> Response:
        checks.append(request)
        version = "1.2.3" if len(checks) == 1 else "1.2.4"
        return Response({"versions": {version: {"dist": {"tarball": "https://registry.npmjs.org/util.tgz"}}}})

    def publish(_call: Command) -> str:
        expected_checks = 2
        assert len(checks) == expected_checks
        release.published(npm=True)
        return ""

    release.serve("https://registry.npmjs.org/%40zyplux%2Futil", metadata)
    release.on("pnpm publish", publish)
    release.publish(consumer.tag)
    release.expect_npm(consumer.dir)
