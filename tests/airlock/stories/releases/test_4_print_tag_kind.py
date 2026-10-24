from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def test_4_1_1_prints_the_registry_kind_of_the_npm_target_that_owns_the_tag(release: ReleaseFixture) -> None:
    assert release.run("print-tag-kind", "util-v1.2.3").stdout.strip() == "npm"


def test_4_1_2_prints_the_registry_kind_of_the_pypi_target_that_owns_the_tag(release: ReleaseFixture) -> None:
    assert release.run("print-tag-kind", "cerberus-v2.3.4").stdout.strip() == "pypi"


def test_4_1_3_prints_the_registry_kind_of_the_ghcr_target_that_owns_the_tag(release: ReleaseFixture) -> None:
    assert release.run("print-tag-kind", "ci-image-v3.4.5").stdout.strip() == "ghcr"


def test_4_1_4_rejects_a_tag_no_release_target_owns(release: ReleaseFixture) -> None:
    release.run(
        "print-tag-kind", "mystery-v1.0.0", error="no release target in airlock-targets.toml owns tag 'mystery-v1.0.0'"
    )
