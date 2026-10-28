from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from cli_fixture import REPO_ROOT, Response

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def test_2_1_1_loads_every_declared_target_reading_versions_from_json_and_toml_manifests(
    release: ReleaseFixture,
) -> None:
    release.all_published()
    assert release.plan() == []


def test_2_2_1_rejects_manifests_without_a_version(release: ReleaseFixture) -> None:
    release.write(
        "airlock_targets.toml",
        """[broken]
kind = "npm"
manifest = "package.json"
""",
    )
    release.write_json("package.json", {"name": "broken-target"})
    release.run("plan", error="version")


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
    release.on("git ls-remote")
    release.action_releases([])
    assert release.plan()
    assert not release.matching("pnpm pack|uv build")


def test_2_5_1_reads_package_names_from_manifests_and_derives_tags_from_table_names(release: ReleaseFixture) -> None:
    release.write_json("packages/util/package.json", {"name": "@demo/custom", "version": "1.2.3"})
    release.published(npm=True)
    assert release.plan("util-v1.2.3")[0]["tags"] == ["util-v1.2.3"]
    assert any(request.url == "https://registry.npmjs.org/%40demo%2Fcustom" for request in release.requests)


def test_2_5_2_honors_package_name_overrides_without_changing_the_release_tag(release: ReleaseFixture) -> None:
    release.configure("npm", 'package_name = "@demo/custom"')
    release.published(npm=True)
    assert release.plan("util-v1.2.3")[0]["tags"] == ["util-v1.2.3"]
    assert any(request.url == "https://registry.npmjs.org/%40demo%2Fcustom" for request in release.requests)


@pytest.mark.parametrize("manifest", ['scope = ""', "scope = 1", "util = 1"])
def test_2_5_3_rejects_malformed_release_declarations(release: ReleaseFixture, manifest: str) -> None:
    release.write("airlock_targets.toml", manifest)
    release.run("plan", error="")


@pytest.mark.parametrize("kind", ["npm", "pypi"])
@pytest.mark.parametrize("location", ["absolute", "parent", "symlink"])
def test_2_5_4_rejects_version_sources_outside_the_repository(
    release: ReleaseFixture, kind: str, location: str
) -> None:
    outside = release.root.with_name(f"{release.root.name}-outside")
    outside.mkdir()
    version_file = outside / "package.json"
    version_file.write_text('{"version":"1.2.3"}', encoding="utf-8")
    match location:
        case "absolute":
            path = str(version_file)
        case "parent":
            path = f"../{outside.name}/package.json"
        case _:
            (release.root / "linked").symlink_to(outside, target_is_directory=True)
            path = "linked/package.json"
    release.configure(kind, f'manifest = "{path}"')
    release.run("plan", error="release paths must be repository-relative")
    assert not release.matching("pnpm pack|uv build|publish")


@pytest.mark.parametrize("command", ["plan", "prepare"])
def test_2_5_5_reports_unsupported_manifest_formats_without_a_traceback(release: ReleaseFixture, command: str) -> None:
    release.configure("pypi", 'manifest = "apps/cerberus/VERSION"')
    release.write("apps/cerberus/VERSION", "2.3.4")
    execution = release.run(command, error="apps/cerberus/VERSION: manifest must be JSON or TOML")
    assert "Traceback" not in execution.stderr


@pytest.mark.parametrize("quote", ['"', "'"])
def test_2_1_2_reads_project_versions_from_parsed_toml(release: ReleaseFixture, quote: str) -> None:
    release.write(
        "apps/cerberus/pyproject.toml",
        f'version = "9.9.9"\n[project]\nname = "zyplux-cerberus"\nversion = {quote}2.3.4{quote}\n',
    )
    assert release.plan("cerberus-v2.3.4")[0]["tags"] == ["cerberus-v2.3.4"]


def test_2_1_3_infers_package_kinds_from_json_and_toml_manifests(release: ReleaseFixture) -> None:
    release.write(
        "airlock_targets.toml",
        release.read("airlock_targets.toml").replace('kind = "npm"\n', "").replace('kind = "pypi"\n', ""),
    )
    assert [(batch["id"], batch["kind"]) for batch in release.plan()][:2] == [
        ("npm-util", "npm"),
        ("pypi-cerberus", "pypi"),
    ]


def test_2_5_6_honors_release_tag_overrides_without_changing_target_names(release: ReleaseFixture) -> None:
    release.use_package()
    release.configure("npm", 'release_tag = "short"')
    release.published()
    batch = release.plan("short-v1.2.3")[0]
    assert batch["id"] == "npm-util"
    release.stage_npm()
    release.publish_batch(batch)
    assert release.matching("gh release create short-v1.2.3")
