from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from cli_fixture import Reply
from release_fixture import MISSING_RELEASE, build_release, capture_release_notes

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


@pytest.fixture
def release(release: ReleaseFixture) -> ReleaseFixture:
    release.action()
    return release


def test_19_1_1_creates_reviewed_release_notes_before_advancing_the_major_alias(release: ReleaseFixture) -> None:
    release.on("gh api graphql", MISSING_RELEASE)
    captured = capture_release_notes(release)
    release.publish("setup-pm-v1.0.0")
    assert captured == ["- Cache package managers.\n"]
    assert [call.text for call in release.matching("git push")] == [
        "git push --force-with-lease=refs/tags/setup-pm-v1:old-sha origin release-sha:refs/tags/setup-pm-v1"
    ]
    assert not release.matching("pnpm pack|pnpm publish|uv build|uv publish")
    assert release.calls.index(release.matching("gh release create")[0]) < release.calls.index(
        release.matching("git push")[0]
    )


def test_19_1_2_repairs_a_missing_alias_when_the_fixed_release_already_exists(release: ReleaseFixture) -> None:
    release.on("git ls-remote origin refs/tags/setup-pm-v1", "")
    release.on("git ls-remote origin refs/tags/setup-pm-v1.0.0*", "release-sha\trefs/tags/setup-pm-v1.0.0")
    release.publish("setup-pm-v1.0.0")
    assert not release.matching("gh release create")
    assert [call.text for call in release.matching("git push")] == [
        "git push --force-with-lease=refs/tags/setup-pm-v1: origin release-sha:refs/tags/setup-pm-v1"
    ]


def test_19_1_3_leaves_a_completed_release_unchanged(release: ReleaseFixture) -> None:
    release.on("git ls-remote origin refs/tags/setup-pm-v1", "release-sha\trefs/tags/setup-pm-v1")
    release.on("git ls-remote origin refs/tags/setup-pm-v1.0.0*", "release-sha\trefs/tags/setup-pm-v1.0.0")
    release.publish("setup-pm-v1.0.0")
    assert release.plan() == []
    assert not release.matching("gh release create|git fetch|git push")


def test_19_1_4_retries_an_older_release_using_the_newest_stable_release_in_its_major_across_all_pages(
    release: ReleaseFixture,
) -> None:
    release.action_releases(
        [build_release(tag) for tag in ("setup-pm-v1.0.0", "setup-pm-v2.0.0", "cz-v99.0.0")],
        [
            build_release("setup-pm-v1.9.0"),
            build_release("setup-pm-v1.10.0"),
            build_release("setup-pm-v1.11.0", draft=True),
            build_release("setup-pm-v1.12.0", prerelease=True),
            build_release("setup-pm-v1.13.0-beta.1"),
            build_release("setup-pm-vinvalid"),
        ],
    )
    release.on("git ls-remote origin refs/tags/setup-pm-v1.10.0*", "newer-sha\trefs/tags/setup-pm-v1.10.0")
    release.on("git rev-parse FETCH_HEAD^{commit}", "newer-sha")
    release.publish("setup-pm-v1.0.0")
    assert [call.text for call in release.matching("git fetch")] == [
        "git fetch --no-tags origin refs/tags/setup-pm-v1.10.0"
    ]
    assert [call.text for call in release.matching("git push")] == [
        "git push --force-with-lease=refs/tags/setup-pm-v1:old-sha origin newer-sha:refs/tags/setup-pm-v1"
    ]


def test_19_1_5_selects_incomplete_action_releases_for_workflow_retries(release: ReleaseFixture) -> None:
    assert [batch["tags"] for batch in release.plan()] == [["setup-pm-v1.0.0"]]
    release.on("git ls-remote origin refs/tags/setup-pm-v1", "release-sha\trefs/tags/setup-pm-v1")
    release.on("git ls-remote origin refs/tags/setup-pm-v1.0.0*", "release-sha\trefs/tags/setup-pm-v1.0.0")
    assert release.plan() == []


def test_19_1_6_promotes_the_commit_behind_an_annotated_versioned_tag(release: ReleaseFixture) -> None:
    release.on(
        "git ls-remote origin refs/tags/setup-pm-v1.0.0*",
        "tag-object\trefs/tags/setup-pm-v1.0.0\nrelease-sha\trefs/tags/setup-pm-v1.0.0^{}",
    )
    release.publish("setup-pm-v1.0.0")
    assert "origin release-sha:refs/tags/setup-pm-v1" in release.matching("git push")[0].text


def test_19_1_7_waits_for_a_newly_created_release_to_appear_before_advancing_its_alias(release: ReleaseFixture) -> None:
    release.on("gh api graphql", MISSING_RELEASE)
    replies = iter([[[]], [[build_release("setup-pm-v1.0.0")]]])
    release.on("gh api --paginate --slurp", lambda _: json.dumps(next(replies)))
    release.publish("setup-pm-v1.0.0")
    assert len(release.matching("gh release create")) == 1
    visibility_attempts = 2
    assert len(release.matching("gh api --paginate --slurp")) == visibility_attempts
    assert len(release.matching("git push")) == 1


@pytest.mark.parametrize(
    "releases",
    [[], [build_release("setup-pm-v1.0.0", draft=True)], [build_release("setup-pm-v1.0.0", prerelease=True)]],
)
def test_19_2_1_requires_a_published_stable_release_before_moving_its_alias(
    release: ReleaseFixture, releases: list[dict[str, object]]
) -> None:
    release.action_releases(releases)
    release.publish("setup-pm-v1.0.0", error="not visible after waiting")
    visibility_attempts = 12
    assert len(release.matching("gh api --paginate --slurp")) == visibility_attempts
    assert not release.matching("git fetch|git push")


def test_19_2_2_leaves_the_alias_unchanged_when_github_release_creation_fails(release: ReleaseFixture) -> None:
    release.on("gh api graphql", MISSING_RELEASE)
    release.on("gh release create", Reply(exit_code=1))
    release.publish("setup-pm-v1.0.0", error="exit code 1")
    assert not release.matching("git fetch|git push")


def test_19_2_3_reports_a_rejected_tag_lease_instead_of_forcing_over_a_concurrent_publisher(
    release: ReleaseFixture,
) -> None:
    release.on("git push", Reply(exit_code=1))
    release.publish("setup-pm-v1.0.0", error="exit code 1")
    assert len(release.matching("git push")) == 1
    assert "--force-with-lease=refs/tags/setup-pm-v1:old-sha" in release.matching("git push")[0].text


def test_19_2_4_refuses_to_publish_a_floating_alias_to_a_changed_versioned_tag(release: ReleaseFixture) -> None:
    release.on("git rev-parse FETCH_HEAD^{commit}", "changed-sha")
    release.publish("setup-pm-v1.0.0", error="changed during publication")
    assert not release.matching("git push")


def test_19_2_5_rejects_invalid_action_versions_before_creating_a_release(release: ReleaseFixture) -> None:
    release.write("apps/action-setup-pm/pyproject.toml", 'version = "1.0.0-beta.1"\n')
    release.write_json(
        "apps/action-setup-pm/package.json", {"name": "zyplux-setup-pm", "private": True, "version": "1.0.0-beta.1"}
    )
    release.write("apps/action-setup-pm/CHANGELOG.md", "## 1.0.0-beta.1\n\n- Publish an action.\n")
    release.publish("setup-pm-v1.0.0-beta.1", error="must be stable semver")
    assert not release.matching("gh release create|git push")


def test_19_2_6_rejects_a_missing_versioned_tag_instead_of_guessing_the_current_commit(release: ReleaseFixture) -> None:
    release.on("git ls-remote origin refs/tags/setup-pm-v1.0.0*", "")
    release.publish("setup-pm-v1.0.0", error="published action tag setup-pm-v1.0.0 is missing")
    assert not release.matching("git push")


def test_19_3_1_synchronizes_the_private_manifest_native_helper_and_lockfiles_without_a_pypi_target(
    release: ReleaseFixture,
) -> None:
    release.prepare_workspace()
    release.write("pyproject.toml", '[tool.uv.workspace]\nmembers = ["apps/cerberus", "apps/action-setup-pm"]\n')
    release.write(
        "apps/action-setup-pm/pyproject.toml",
        '[project]\nname = "zyplux-setup-pm"\nversion = "1.0.0"\nrequires-python = ">=3.14"\n',
    )
    release.write(
        ".changeset/action.md", '---\n"zyplux-setup-pm": patch\n---\n\nCache compatible package-manager releases.\n'
    )
    release.run("prepare")
    assert json.loads(release.read("apps/action-setup-pm/package.json"))["version"] == "1.0.1"
    assert 'version = "1.0.1"' in release.read("apps/action-setup-pm/pyproject.toml")
    assert "Cache compatible package-manager releases." in release.read("apps/action-setup-pm/CHANGELOG.md")
    assert "apps/action-setup-pm" in release.read("pnpm-lock.yaml")
    assert 'version = "1.0.1"' in release.read("uv.lock")
    assert not (release.root / ".changeset/action.md").exists()
