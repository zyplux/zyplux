from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from release_fixture import MISSING_RELEASE, capture_release_notes

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def test_17_1_2_preserves_markdown_examples_and_excludes_neighboring_release_versions(release: ReleaseFixture) -> None:
    release.write(
        "packages/util/CHANGELOG.md",
        "# Utility\n\n## 1.2.3\n\n- Preserve examples.\n\n"
        "```md\n## 9.9.9\n- Example heading.\n```\n\n## 1.2.2\n\n- Earlier release.\n",
    )
    captured = capture_release_notes(release)
    release.stage_npm()
    release.publish("util-v1.2.3")
    assert captured == ["- Preserve examples.\n\n```md\n## 9.9.9\n- Example heading.\n```\n"]


def test_17_2_2_rejects_unconsumed_fragments(release: ReleaseFixture) -> None:
    release.write(".changeset/unfinished.md", '---\n"@zyplux/util": patch\n---\n\nFix a utility.\n')
    release.run("plan", error="Unconsumed change intents: .changeset/unfinished.md")


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
    execution = release.run("plan", error="")
    assert "no release notes" in execution.stderr or "no changelog entries" in execution.stderr


@pytest.mark.parametrize("override", [{"version": "2.3.5"}, {"name": "another-package"}, {"private": False}])
def test_17_2_4_rejects_inconsistent_python_tracking_manifests(
    release: ReleaseFixture, override: dict[str, object]
) -> None:
    release.write_json(
        "apps/cerberus/package.json", {"name": "zyplux-cerberus", "private": True, "version": "2.3.4", **override}
    )
    release.run("plan", error="")


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
    release.publish(tag)
    assert captured == [f"### Patch Changes\n\n- {notes}\n"]
    release.expect_release(tag)


@pytest.mark.parametrize(("tag", "directory"), [("util-v1.2.3", "packages/util"), ("cerberus-v2.3.4", "apps/cerberus")])
def test_17_3_2_rejects_missing_notes_before_publication(release: ReleaseFixture, tag: str, directory: str) -> None:
    release.all_published(pypi=False)
    release.write(f"{directory}/CHANGELOG.md", "# Releases\n")
    release.publish(tag, error="no release notes")
    assert not release.matching("gh release create|pnpm publish|uv publish|podman build")
