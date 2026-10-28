from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
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
    configure_private_registry(release)
    release.on("pnpm version", Reply(exit_code=1))
    release.run("prepare", error="command failed")
    assert release.matching("pnpm version -r --no-git-checks --config.@zyplux:registry=https://npm.pkg.github.com")
    assert not release.matching("pnpm install|uv")


def configure_private_registry(release: ReleaseFixture) -> None:
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


@pytest.mark.parametrize("source", ["NODE_AUTH_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "gh"])
def test_18_1_6_authenticates_private_preparation_with_existing_github_credentials(
    release: ReleaseFixture, source: str
) -> None:
    configure_private_registry(release)
    if source == "gh":
        release.on("gh auth token", release.credential)
    else:
        release.env[source] = release.credential
    public_auth = {"https://registry.npmjs.org": {"@": {"authToken": "public-token"}}}
    release.env["PNPM_CONFIG__AUTH"] = json.dumps(public_auth)
    release.run("prepare")
    for command in release.matching("pnpm version|pnpm install"):
        assert json.loads(command.env["pnpm_config__auth"]) == {
            **public_auth,
            "https://npm.pkg.github.com": {"@zyplux": {"authToken": release.credential}},
        }
        assert release.credential not in command.text
    assert "pnpm_config__auth" not in release.env
    assert not release.matching("uv")[0].env
    assert not (release.root / ".npmrc").exists()


@pytest.mark.parametrize("source", ["environment", "npmrc", "global", "url-environment"])
@pytest.mark.parametrize("scope", ["@", "@zyplux"])
def test_18_1_7_preserves_explicit_registry_authentication(release: ReleaseFixture, source: str, scope: str) -> None:
    configure_private_registry(release)
    auth = {"https://npm.pkg.github.com/": {scope: {"authToken": "caller-token"}}}
    if source == "environment":
        release.env["pnpm_config__auth"] = json.dumps(auth)
    elif source == "global":
        release.write_json("pnpm-config.yaml", {"_auth": auth})
    elif source == "npmrc":
        prefix = "" if scope == "@" else f"{scope}:"
        release.on("pnpm config list --json", json.dumps({f"//npm.pkg.github.com/:{prefix}_authToken": "(protected)"}))
    else:
        prefix = "" if scope == "@" else f"{scope}:"
        release.env[f"pnpm_config_//npm.pkg.github.com/:{prefix}_authToken"] = "caller-token"
    release.env["GH_TOKEN"] = release.credential
    release.run("prepare")
    assert all(not command.env for command in release.matching("pnpm version|pnpm install"))
    assert not release.matching("gh auth token")


def test_18_1_8_keeps_public_preparation_independent_of_github_credentials(release: ReleaseFixture) -> None:
    release.env["GH_TOKEN"] = release.credential
    release.run("prepare")
    assert not release.matching("pnpm config|gh auth token")
    assert all(not command.env for command in release.matching("pnpm version|pnpm install"))


def test_18_1_9_prepares_without_a_github_login_when_no_fallback_is_available(release: ReleaseFixture) -> None:
    configure_private_registry(release)
    release.run("prepare")
    assert release.matching("gh auth token")
    assert all(not command.env for command in release.matching("pnpm version|pnpm install"))


@pytest.mark.parametrize("variable", ["pnpm_config__auth", "PNPM_CONFIG__AUTH"])
def test_18_1_10_rejects_invalid_authentication_without_disclosing_credentials(
    release: ReleaseFixture, variable: str
) -> None:
    configure_private_registry(release)
    release.env[variable] = release.credential
    execution = release.run("prepare", error="Cannot read pnpm registry authentication configuration")
    assert release.credential not in execution.stdout + execution.stderr
    assert not release.matching("pnpm")


def test_18_1_11_adds_only_missing_scope_credentials_and_honors_lowercase_environment_precedence(
    release: ReleaseFixture,
) -> None:
    configure_private_registry(release)
    auth = {"https://npm.pkg.github.com/": {"@other": {"authToken": "other-token"}}}
    release.env.update(
        pnpm_config__auth=json.dumps(auth),
        PNPM_CONFIG__AUTH="invalid-ignored-uppercase",
        NODE_AUTH_TOKEN=release.credential,
        GH_TOKEN=release.credential[::-1],
    )
    release.run("prepare")
    for command in release.matching("pnpm version|pnpm install"):
        assert json.loads(command.env["pnpm_config__auth"]) == {
            **auth,
            "https://npm.pkg.github.com": {"@zyplux": {"authToken": release.credential}},
        }


@pytest.mark.parametrize("scope_registry", [None, "https://registry.example.com"])
def test_18_1_12_adds_authentication_without_changing_dependency_registry_routes(
    release: ReleaseFixture, scope_registry: str | None
) -> None:
    configure_private_registry(release)
    release.env["GH_TOKEN"] = release.credential
    configured = {"registry": "https://registry.npmjs.org"}
    if scope_registry:
        configured["@zyplux:registry"] = scope_registry
    release.on("pnpm config list --json", json.dumps(configured))
    release.run("prepare")
    versioning = release.matching("pnpm version")[0]
    install = release.matching("pnpm install")[0]
    assert "--config.@zyplux:registry=https://npm.pkg.github.com" in versioning.text
    dependency_registry = scope_registry or configured["registry"]
    assert install.text == f"pnpm install --lockfile-only --config.@zyplux:registry={dependency_registry}"
    assert json.loads(install.env["pnpm_config__auth"]) == {
        "https://npm.pkg.github.com": {"@zyplux": {"authToken": release.credential}}
    }
