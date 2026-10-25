from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from cli_fixture import REPO_ROOT, Response

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def test_2_1_1_loads_every_declared_target_reading_versions_from_json_and_regex_sources(
    release: ReleaseFixture,
) -> None:
    release.all_published()
    assert release.plan() == []


def test_2_2_1_rejects_reading_a_version_whose_regex_does_not_match_the_file(release: ReleaseFixture) -> None:
    release.write(
        "airlock-targets.toml",
        """scope = "@zyplux"
[broken]
kind = "npm"
label = "broken-target"
surface = []
version = { file = "VERSION", regex = '^nomatch$' }
""",
    )
    release.write("VERSION", "1.2.3\n")
    release.run("plan", error="could not read version from VERSION")


def test_2_3_1_rejects_finalized_releases_when_their_image_cannot_be_accessed(release: ReleaseFixture) -> None:
    release.all_published()
    release.serve("https://ghcr.io/token", Response(status=404))
    release.plan(error="is missing image")


@pytest.mark.parametrize("credential", ["GH_TOKEN", "NODE_AUTH_TOKEN"])
def test_2_3_2_authenticates_private_image_probes_and_propagates_registry_failures(
    release: ReleaseFixture, credential: str
) -> None:
    release.all_published()
    release.env.update({credential: "read-token", "GITHUB_ACTOR": "bot"})
    release.serve("https://ghcr.io/token", Response({"token": "private-token"}))
    release.serve("https://ghcr.io/v2/", Response(status=403))
    release.plan("ci-image-v3.4.5", error="403")
    request = next(request for request in release.requests if request.url.startswith("https://ghcr.io/token"))
    assert request.method == "GET"
    assert request.headers["authorization"] == "Basic Ym90OnJlYWQtdG9rZW4="


def test_2_4_1_loads_a_version_for_every_target_declared_in_airlock_targets_toml(release: ReleaseFixture) -> None:
    release.on("git rev-parse --show-toplevel", str(REPO_ROOT))
    release.run("check")
    assert not release.requests


def test_2_5_1_derives_labels_from_the_configured_scope_and_tags_from_table_names(release: ReleaseFixture) -> None:
    release.write(
        "airlock-targets.toml", release.read("airlock-targets.toml").replace('scope = "@zyplux"', 'scope = "@demo"')
    )
    release.published(npm=True)
    assert release.plan("util-v1.2.3")[0]["tags"] == ["util-v1.2.3"]
    assert any(request.url == "https://registry.npmjs.org/%40demo%2Futil" for request in release.requests)


def test_2_5_2_honors_explicit_labels_without_changing_the_derived_tag_prefix(release: ReleaseFixture) -> None:
    release.configure("npm", 'label = "@demo/custom"')
    release.published(npm=True)
    assert release.plan("util-v1.2.3")[0]["tags"] == ["util-v1.2.3"]
    assert any(request.url == "https://registry.npmjs.org/%40demo%2Fcustom" for request in release.requests)


@pytest.mark.parametrize("manifest", ["", 'scope = ""', "scope = 1", 'scope = "@demo"\nutil = 1'])
def test_2_5_3_rejects_malformed_release_declarations(release: ReleaseFixture, manifest: str) -> None:
    release.write("airlock-targets.toml", manifest)
    release.run("check", error="")
