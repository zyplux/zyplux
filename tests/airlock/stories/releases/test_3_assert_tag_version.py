from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def test_3_1_1_logs_a_confirmation_when_the_tag_matches_its_targets_declared_version(release: ReleaseFixture) -> None:
    execution = release.run("assert-tag-version", "util-v1.2.3")
    assert "@zyplux/util 1.2.3 matches util-v1.2.3" in execution.stdout


def test_3_1_2_rejects_a_tag_no_release_target_owns(release: ReleaseFixture) -> None:
    release.run(
        "assert-tag-version",
        "mystery-v1.0.0",
        error="no release target in airlock-targets.toml owns tag 'mystery-v1.0.0'",
    )


def test_3_1_3_rejects_a_tag_whose_version_does_not_match_the_manifest(release: ReleaseFixture) -> None:
    release.run("assert-tag-version", "cerberus-v0.0.0-does-not-exist", error="does not match zyplux-cerberus version")
