from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def test_5_1_1_rejects_a_label_no_release_target_owns(release: ReleaseFixture) -> None:
    release.run(
        "bootstrap-npm-target",
        "does-not-exist",
        error="no release target labeled 'does-not-exist' in airlock-targets.toml",
    )


def test_5_1_2_rejects_a_target_that_is_not_an_npm_target(release: ReleaseFixture) -> None:
    release.run(
        "bootstrap-npm-target", "zyplux-cerberus", error="bootstrap is npm-only; 'zyplux-cerberus' is a pypi target"
    )


def test_5_2_1_skips_publishing_when_the_targets_version_is_already_on_npm(release: ReleaseFixture) -> None:
    release.published(npm=True)
    assert "already published; no bootstrap needed" in release.run("bootstrap-npm-target", "@zyplux/util").stdout
    assert not release.matching("pnpm pack")


def test_5_2_2_publishes_the_target_with_the_terminal_connected_for_npm_authentication(release: ReleaseFixture) -> None:
    release.stage_npm()
    execution = release.run("bootstrap-npm-target", "@zyplux/util", stdin="authentication-code\n")
    release.expect_npm()
    assert release.matching("^pnpm publish")[0].stdin == "authentication-code\n"
    assert (
        "Published @zyplux/util 1.2.3. Configure registry authentication in the release workflow." in execution.stdout
    )
