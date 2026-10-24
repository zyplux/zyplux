from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from release_fixture import MISSING_RELEASE, capture_release_notes

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def test_17_1_1_emits_version_specific_notes_and_target_metadata_without_registry_access(
    release: ReleaseFixture,
) -> None:
    prepared = json.loads(release.run("list-prepared-releases").stdout)
    assert prepared == [
        {
            "kind": "npm",
            "label": "@zyplux/util",
            "version": "1.2.3",
            "tag": "util-v1.2.3",
            "notes": "### Patch Changes\n\n- Publish the reviewed utility changes.",
        },
        {
            "kind": "pypi",
            "label": "zyplux-cerberus",
            "version": "2.3.4",
            "tag": "cerberus-v2.3.4",
            "notes": "### Patch Changes\n\n- Validate repository release contracts.",
        },
        {
            "kind": "ghcr",
            "label": "ghcr.io/zyplux/ci",
            "version": "3.4.5",
            "tag": "ci-image-v3.4.5",
            "notes": "### Patch Changes\n\n- Refresh the CI container.",
        },
    ]
    assert not release.requests


def test_17_1_2_preserves_markdown_examples_and_excludes_neighboring_release_versions(release: ReleaseFixture) -> None:
    release.write(
        "packages/util/CHANGELOG.md",
        "# Utility\n\n## 1.2.3\n\n- Preserve examples.\n\n"
        "```md\n## 9.9.9\n- Example heading.\n```\n\n## 1.2.2\n\n- Earlier release.\n",
    )
    prepared = release.run("list-prepared-releases").stdout
    assert "Preserve examples." in prepared
    assert "Example heading." in prepared
    assert "Earlier release." not in prepared


def test_17_2_1_validates_prepared_releases_without_writes_or_network_requests(release: ReleaseFixture) -> None:
    assert not release.run("check-release-notes").stdout
    assert not release.requests
    assert not release.matching("gh|pnpm|uv")


def test_17_2_2_rejects_unconsumed_fragments(release: ReleaseFixture) -> None:
    release.write(".changeset/unfinished.md", '---\n"@zyplux/util": patch\n---\n\nFix a utility.\n')
    release.run("check-release-notes", error="Unconsumed change intents: .changeset/unfinished.md")


@pytest.mark.parametrize(
    "markdown",
    [
        "## 1.2.2\n\n- Earlier notes.\n",
        "## 1.2.3\n\n### Patch Changes\n",
        "## 1.2.3\n\n-\n",
        "## 1.2.3\n\n```md\n- Example text.\n```\n",
    ],
)
def test_17_2_3_rejects_a_changelog_without_release_entries(release: ReleaseFixture, markdown: str) -> None:
    release.write("packages/util/CHANGELOG.md", markdown)
    execution = release.run("check-release-notes", error="")
    assert "no release notes" in execution.stderr or "no changelog entries" in execution.stderr


@pytest.mark.parametrize("override", [{"version": "2.3.5"}, {"name": "another-package"}, {"private": False}])
def test_17_2_4_rejects_inconsistent_python_tracking_manifests(
    release: ReleaseFixture, override: dict[str, object]
) -> None:
    release.write_json(
        "apps/cerberus/package.json", {"name": "zyplux-cerberus", "private": True, "version": "2.3.4", **override}
    )
    release.run("check-release-notes", error="")


@pytest.mark.parametrize(
    ("tag", "notes"),
    [
        ("util-v1.2.3", "Publish the reviewed utility changes."),
        ("cerberus-v2.3.4", "Validate repository release contracts."),
    ],
)
def test_17_3_1_sends_the_exact_target_entry_to_github(release: ReleaseFixture, tag: str, notes: str) -> None:
    release.all_published(pypi=False)
    release.on("gh api graphql", MISSING_RELEASE)
    release.on("uv build")
    release.on("uv publish")
    captured = capture_release_notes(release)
    release.run("publish-tagged-target", "--release", tag)
    assert captured == [f"### Patch Changes\n\n- {notes}\n"]
    release.expect_release(tag)


@pytest.mark.parametrize(("tag", "directory"), [("util-v1.2.3", "packages/util"), ("cerberus-v2.3.4", "apps/cerberus")])
def test_17_3_2_rejects_missing_notes_before_publication(release: ReleaseFixture, tag: str, directory: str) -> None:
    release.all_published(pypi=False)
    release.write(f"{directory}/CHANGELOG.md", "# Releases\n")
    release.run("publish-tagged-target", "--release", tag, error="no release notes")
    assert not release.matching("gh release create|pnpm publish|uv publish|podman build")
