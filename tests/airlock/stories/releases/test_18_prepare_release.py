from __future__ import annotations

import json
from typing import TYPE_CHECKING

from cli_fixture import Reply

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def test_18_1_1_runs_pnpm_versioning_and_uv_to_produce_synchronized_versions_changelogs_and_lockfiles(
    release: ReleaseFixture,
) -> None:
    release.prepare_workspace()
    release.run("prepare")
    assert json.loads(release.read("packages/util/package.json"))["version"] == "1.3.0"
    assert json.loads(release.read("apps/cerberus/package.json"))["version"] == "2.3.5"
    assert "Expose reviewed target release notes." in release.read("packages/util/CHANGELOG.md")
    assert 'version = "2.3.5"' in release.read("apps/cerberus/pyproject.toml")
    assert "apps/cerberus" in release.read("pnpm-lock.yaml")
    assert 'version = "2.3.5"' in release.read("uv.lock")
    assert not (release.root / ".changeset/feature.md").exists()
    assert release.matching("pnpm version -r --no-git-checks --config.@zyplux:registry=https://registry.npmjs.org")
    changelog = release.read("packages/util/CHANGELOG.md")
    release.run("prepare")
    assert release.read("packages/util/CHANGELOG.md") == changelog


def test_18_1_2_rejects_python_version_drift_before_changing_any_release_files(release: ReleaseFixture) -> None:
    release.write_json("apps/cerberus/package.json", {"name": "zyplux-cerberus", "private": True, "version": "2.4.0"})
    release.run("prepare", error="package.json and pyproject.toml versions must match")
    assert not release.matching("node|pnpm|uv")


def test_18_1_3_stops_before_python_synchronization_when_native_versioning_fails(release: ReleaseFixture) -> None:
    release.prepare_workspace()
    release.on("pnpm version", Reply(stdout="Registry lookup failed.", exit_code=1))
    execution = release.run("prepare", error="command failed")
    assert "Registry lookup failed." in execution.stderr
    assert 'version = "2.3.4"' in release.read("apps/cerberus/pyproject.toml")
    assert not release.matching("pnpm install|uv")


def test_18_1_4_propagates_a_workspace_dependency_bump_through_pnpm(release: ReleaseFixture) -> None:
    release.prepare_workspace()
    release.write_json(
        "packages/consumer/package.json",
        {
            "dependencies": {"@zyplux/util": "workspace:*"},
            "name": "release-consumer",
            "private": True,
            "version": "5.0.0",
        },
    )
    release.run("prepare")
    assert json.loads(release.read("packages/consumer/package.json"))["version"] == "5.0.1"
    assert "@zyplux/util@1.3.0" in release.read("packages/consumer/CHANGELOG.md")


def test_18_1_5_directs_version_lookups_to_the_package_publication_registry(release: ReleaseFixture) -> None:
    release.write_json(
        "packages/util/package.json",
        {
            "name": "@zyplux/util",
            "version": "1.2.3",
            "publishConfig": {
                "@zyplux:registry": "https://npm.pkg.github.com",
                "registry": "https://registry.npmjs.org",
            },
        },
    )
    release.on("pnpm version", Reply(exit_code=1))
    release.run("prepare", error="command failed")
    assert release.matching("pnpm version -r --no-git-checks --config.@zyplux:registry=https://npm.pkg.github.com")
    assert not release.matching("pnpm install|uv")
