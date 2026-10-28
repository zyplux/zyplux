from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
import yaml
from archive_fixture import stage_git
from cli_fixture import Command, Reply, Response
from release_fixture import build_release

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


@pytest.mark.parametrize("sequential", [False, True])
@pytest.mark.parametrize(("bump", "version"), [("patch", "1.2.4"), ("minor", "1.3.0")])
def test_18_2_1_consolidates_sequential_and_batched_intents_from_one_baseline(
    release: ReleaseFixture, *, sequential: bool, bump: str, version: str
) -> None:
    release.prepare_workspace()
    release.write(".changeset/feature.md", '---\n"@zyplux/util": patch\n---\n\nFirst note.\n')
    release.write("packages/util/index.js", "first source\n")
    if sequential:
        release.run("prepare")
    release.write("packages/util/index.js", "updated source\n")
    release.write(".changeset/second.md", f'---\n"@zyplux/util": {bump}\n---\n\nSecond note.\n')
    release.run("prepare")
    assert json.loads(release.read("packages/util/package.json"))["version"] == version
    changelog = release.read("packages/util/CHANGELOG.md")
    assert changelog.count("First note.") == changelog.count("Second note.") == 1
    assert changelog.count(f"## {version}\n") == 1
    assert "## 1.2.3\n" in changelog
    if version == "1.3.0":
        assert "## 1.2.4\n" not in changelog
    prepared = capture_metadata(release)
    release.run("prepare")
    assert capture_metadata(release) == prepared


def test_18_2_2_replans_dependency_bumps_and_preserves_manifest_source_edits(release: ReleaseFixture) -> None:
    release.prepare_workspace()
    release.write_json(
        "packages/consumer/package.json",
        {"name": "consumer", "private": True, "version": "4.0.0", "dependencies": {"@zyplux/util": "workspace:*"}},
    )
    release.run("prepare")
    manifest = json.loads(release.read("packages/util/package.json"))
    manifest["description"] = "Preserve this user edit"
    release.write_json("packages/util/package.json", manifest)
    release.write(".changeset/another.md", '---\n"@zyplux/util": patch\n---\n\nMore notes.\n')
    release.run("prepare")
    assert json.loads(release.read("packages/util/package.json"))["version"] == "1.3.0"
    assert json.loads(release.read("packages/util/package.json"))["description"] == "Preserve this user edit"
    assert json.loads(release.read("packages/consumer/package.json"))["version"] == "4.0.1"
    assert release.read("packages/consumer/CHANGELOG.md").count("## 4.0.1") == 1


@pytest.mark.parametrize("step", ["pnpm install", "uv lock", "pnpm pack"])
@pytest.mark.parametrize("has_preparation", [False, True])
def test_18_2_3_restores_release_metadata_and_preserves_user_changes_after_failure(
    release: ReleaseFixture, step: str, *, has_preparation: bool
) -> None:
    release.prepare_workspace()
    if has_preparation:
        release.run("prepare")
        release.write(".changeset/next.md", '---\n"@zyplux/util": patch\n---\n\nNext note.\n')
    stage_git(release)
    release.write("packages/util/index.js", "staged source\n")
    assert release.run_real(Command("git", ["add", "packages/util"], str(release.root))).exit_code == 0
    release.write("packages/util/index.js", "unstaged source\n")
    release.write("untracked.txt", "Preserve this untracked file.\n")
    manifest = json.loads(release.read("packages/util/package.json"))
    manifest["description"] = "Unstaged manifest edit"
    release.write_json("packages/util/package.json", manifest)
    before = capture_metadata(release)
    index = (release.root / ".git/index").read_bytes()
    release.on(step, Reply(stderr="Preparation failed.", exit_code=1))
    release.run("prepare", error="Preparation failed.")
    assert capture_metadata(release) == before
    assert (release.root / ".git/index").read_bytes() == index
    assert release.read("packages/util/index.js") == "unstaged source\n"
    assert release.read("untracked.txt") == "Preserve this untracked file.\n"


def test_18_2_4_preserves_metadata_when_a_real_prepack_hook_fails(release: ReleaseFixture) -> None:
    release.prepare_workspace()
    manifest = json.loads(release.read("packages/util/package.json"))
    manifest["scripts"] = {"prepack": "exit 1"}
    release.write_json("packages/util/package.json", manifest)
    before = capture_metadata(release)
    release.on("pnpm pack", release.run_real)
    release.run("prepare", error="command failed")
    assert capture_metadata(release) == before


@pytest.mark.parametrize("publication", ["releases", "artifacts"])
def test_18_2_5_starts_a_new_baseline_after_publication(release: ReleaseFixture, publication: str) -> None:
    release.prepare_workspace()
    release.run("prepare")
    if publication == "releases":
        release.action_releases([build_release("util-v1.3.0"), build_release("cerberus-v2.3.5")])
    else:
        release.serve("https://registry.npmjs.org/", Response({"versions": {"1.3.0": {}}}))
        release.serve("https://pypi.org/", Response({"urls": [{"packagetype": "bdist_wheel"}]}))
    release.write(".changeset/next.md", '---\n"@zyplux/util": patch\n---\n\nNext release.\n')
    release.run("prepare")
    assert json.loads(release.read("packages/util/package.json"))["version"] == "1.3.1"
    changelog = release.read("packages/util/CHANGELOG.md")
    assert "## 1.3.0\n" in changelog
    assert changelog.count("Expose reviewed target release notes.") == changelog.count("Next release.") == 1
    assert 'version = "2.3.5"' in release.read("apps/cerberus/pyproject.toml")


def test_18_2_6_refuses_to_rewind_a_partially_published_preparation(release: ReleaseFixture) -> None:
    release.prepare_workspace()
    release.run("prepare")
    release.serve("https://pypi.org/", Response({"urls": [{"packagetype": "bdist_wheel"}]}))
    release.write(".changeset/next.md", '---\n"@zyplux/util": patch\n---\n\nNext release.\n')
    before = capture_metadata(release)
    release.run("prepare", error="partially published releases")
    assert capture_metadata(release) == before


def test_18_2_7_requires_the_latest_baseline_when_a_newer_version_was_published(release: ReleaseFixture) -> None:
    release.prepare_workspace()
    release.run("prepare")
    release.action_releases([build_release("util-v1.4.0")])
    release.write(".changeset/next.md", '---\n"@zyplux/util": patch\n---\n\nNext release.\n')
    before = capture_metadata(release)
    release.run("prepare", error="merge the latest target branch")
    assert capture_metadata(release) == before


@pytest.mark.parametrize("is_published", [False, True])
def test_18_2_8_requires_legacy_pending_releases_to_publish_before_adoption(
    release: ReleaseFixture, *, is_published: bool
) -> None:
    release.prepare_workspace()
    release.run("prepare")
    (release.root / ".changeset/preparation.json").unlink()
    release.write(".changeset/next.md", '---\n"@zyplux/util": patch\n---\n\nNext release.\n')
    if is_published:
        release.action_releases([build_release("util-v1.3.0"), build_release("cerberus-v2.3.5")])
        release.run("prepare")
        assert json.loads(release.read("packages/util/package.json"))["version"] == "1.3.1"
    else:
        before = capture_metadata(release)
        release.run("prepare", error="pending release has no preparation record")
        assert capture_metadata(release) == before


def test_18_2_9_preserves_overlapping_manual_release_edits_when_replay_conflicts(release: ReleaseFixture) -> None:
    release.prepare_workspace()
    release.run("prepare")
    release.write(
        "packages/util/CHANGELOG.md",
        release.read("packages/util/CHANGELOG.md").replace("Expose reviewed target release notes.", "Manual notes."),
    )
    release.write(".changeset/next.md", '---\n"@zyplux/util": patch\n---\n\nNext note.\n')
    before = capture_metadata(release)
    release.run("prepare", error="edits overlap prepared metadata")
    assert capture_metadata(release) == before


def test_18_2_10_removes_new_release_metadata_on_reported_failure(release: ReleaseFixture) -> None:
    release.prepare_workspace()
    release.write(".changeset/changelogs/existing.md", "Keep this user file.\n")
    before = capture_metadata(release)

    def fail(_: Command) -> Reply:
        release.write(".changeset/changelogs/generated.json", "{}\n")
        release.write(".changeset/changelogs/existing.md", "Changed during preparation.\n")
        return Reply(stderr="Lockfile failed.", exit_code=1)

    release.on("pnpm install", fail)
    release.run("prepare", error="Lockfile failed.")
    assert capture_metadata(release) == before


def test_18_2_11_freezes_an_action_version_tag_before_release_finalization(release: ReleaseFixture) -> None:
    release.prepare_workspace()
    release.configure("npm", 'kind = "action"')
    release.run("prepare")
    release.on("git ls-remote origin refs/tags/util-v1.3.0", "published-sha\trefs/tags/util-v1.3.0")
    before = capture_metadata(release)
    release.run("prepare", error="partially published releases")
    assert capture_metadata(release) == before


def test_18_2_12_preserves_preparation_inputs_when_authentication_bootstrap_fails(release: ReleaseFixture) -> None:
    release.prepare_workspace()
    configure_private_registry(release)
    before = capture_metadata(release)

    def fail(_: Command) -> Reply:
        release.write("pnpm-lock.yaml", "Bootstrap changed the lockfile.\n")
        return Reply(stderr="Bootstrap failed.", exit_code=1)

    release.on("pnpm config list", fail)
    release.run("prepare", error="Bootstrap failed.")
    assert capture_metadata(release) == before


def test_18_2_13_replays_preparation_after_ledger_formatting(release: ReleaseFixture) -> None:
    release.prepare_workspace()
    release.run("prepare")
    ledger = yaml.safe_load(release.read(".changeset/ledger.yaml"))
    release.write(".changeset/ledger.yaml", yaml.safe_dump(ledger, default_style='"'))
    release.write(".changeset/next.md", '---\n"@zyplux/util": patch\n---\n\nAdditional note.\n')
    release.run("prepare")
    assert json.loads(release.read("packages/util/package.json"))["version"] == "1.3.0"
    changelog = release.read("packages/util/CHANGELOG.md")
    assert changelog.count("Expose reviewed target release notes.") == changelog.count("Additional note.") == 1


def capture_metadata(release: ReleaseFixture) -> dict[str, bytes]:
    names = {
        "package.json",
        "pyproject.toml",
        "CHANGELOG.md",
        "pnpm-lock.yaml",
        "pnpm-workspace.yaml",
        "uv.lock",
        "airlock_targets.toml",
    }
    return {
        str(path.relative_to(release.root)): path.read_bytes()
        for directory in (release.root, release.root / "packages/util", release.root / "apps/cerberus")
        for path in directory.iterdir()
        if path.is_file() and path.name in names
    } | {
        str(path.relative_to(release.root)): path.read_bytes()
        for path in (release.root / ".changeset").rglob("*")
        if path.is_file()
    }
