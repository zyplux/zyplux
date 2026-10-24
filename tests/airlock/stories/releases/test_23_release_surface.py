from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest
from cli_fixture import Reply, Response
from release_fixture import build_release

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture

DONE = {"message": "every published target's version tracks its surface", "status": "pass"}


@pytest.fixture
def release(release: ReleaseFixture) -> ReleaseFixture:
    release.surface()
    return release


@pytest.mark.parametrize("manifest", ["not = valid = toml", "", 'scope = ""', "scope = 1", 'scope = "@demo"\nutil = 1'])
def test_23_1_1_rejects_malformed_manifests(release: ReleaseFixture, manifest: str) -> None:
    release.write("airlock-targets.toml", manifest)
    assert [finding["status"] for finding in release.check_surface()] == ["error"]


def test_23_1_2_accepts_a_scope_with_no_targets(release: ReleaseFixture) -> None:
    release.write("airlock-targets.toml", 'scope = "@zyplux"')
    assert release.check_surface() == [DONE]


@pytest.mark.parametrize(
    "manifest", ["invalid json", "{}", '{"version":42}', '{"version":"invalid"}', '{"version":"1.2.3-beta.1"}']
)
def test_23_1_3_rejects_missing_or_invalid_versions(release: ReleaseFixture, manifest: str) -> None:
    release.write("packages/util/package.json", manifest)
    assert [finding["status"] for finding in release.check_surface()] == ["fail"]


def test_23_1_4_reports_missing_version_files(release: ReleaseFixture) -> None:
    release.configure("npm", 'version = { file = "missing.json", json = "version" }')
    findings = release.check_surface()
    assert findings[0]["status"] == "fail"
    assert "missing.json" in findings[0]["message"]


def test_23_1_5_reads_native_python_versions_with_the_configured_regex(release: ReleaseFixture) -> None:
    release.configure(
        "npm",
        """kind = "pypi"
label = "zyplux-cerberus"
version = { file = "apps/cerberus/pyproject.toml", regex = '^version = "([^"]+)"' }""",
    )
    release.published_version("2.3.3")
    assert {
        "message": "zyplux-cerberus: 2.3.4 is ahead of published 2.3.3",
        "status": "pass",
    } in release.check_surface()


def test_23_1_6_validates_every_target_when_one_version_is_invalid(release: ReleaseFixture) -> None:
    release.write_json("packages/util/package.json", {"version": "1.2.4"})
    release.write(
        "airlock-targets.toml",
        release.read("airlock-targets.toml")
        + '\n[broken]\nkind = "npm"\nsurface = []\nversion = { file = "missing.json", json = "version" }\n',
    )
    findings = release.check_surface()
    assert findings[0] == {"message": "@zyplux/util: 1.2.4 is ahead of published 1.2.3", "status": "pass"}
    assert findings[1]["status"] == "fail"
    assert "@zyplux/broken" in findings[1]["message"]


@pytest.mark.parametrize("version", ["1.2.4", "1.3.0", "2.0.0"])
def test_23_2_1_accepts_a_single_patch_minor_or_major_bump(release: ReleaseFixture, version: str) -> None:
    release.write_json("packages/util/package.json", {"version": version})
    assert release.check_surface() == [
        {"message": f"@zyplux/util: {version} is ahead of published 1.2.3", "status": "pass"},
        DONE,
    ]


@pytest.mark.parametrize("version", ["1.2.5", "1.4.0", "3.0.0", "1.3.1"])
def test_23_2_2_rejects_skipped_bumps(release: ReleaseFixture, version: str) -> None:
    release.write_json("packages/util/package.json", {"version": version})
    assert release.check_surface() == [
        {
            "message": f"@zyplux/util: version {version} skips ahead of published 1.2.3 — "
            "bump one step (1.2.4, 1.3.0, or 2.0.0)",
            "status": "fail",
        }
    ]


def test_23_2_3_rejects_versions_below_the_published_version(release: ReleaseFixture) -> None:
    release.published_version("1.10.0")
    assert release.check_surface() == [
        {"message": "@zyplux/util: version 1.2.3 is below published 1.10.0", "status": "fail"}
    ]


def test_23_2_4_permits_an_initial_release(release: ReleaseFixture) -> None:
    release.published_version()
    assert release.check_surface() == [{"message": "@zyplux/util: not yet released", "status": "pass"}, DONE]


def test_23_2_5_accepts_published_versions_with_unchanged_surfaces(release: ReleaseFixture) -> None:
    assert release.check_surface() == [DONE]


def test_23_2_6_rejects_changes_to_an_already_published_version(release: ReleaseFixture) -> None:
    release.on("git diff --name-only util-v1.2.3 -- packages/util/src", "packages/util/src/index.ts")
    assert release.check_surface() == [
        {
            "message": "@zyplux/util: surface changed since util-v1.2.3 "
            "but version is still 1.2.3 — bump it (e.g. 1.2.4)",
            "status": "fail",
        }
    ]


def test_23_2_7_reports_unavailable_release_history(release: ReleaseFixture) -> None:
    release.on("git diff", Reply(exit_code=1))
    findings = release.check_surface()
    assert findings[0]["status"] == "error"
    assert "cannot diff against util-v1.2.3" in findings[0]["message"]


@pytest.mark.parametrize(
    ("base", "current", "published"),
    [("1.2.4", "1.2.4", "1.2.3"), ("2.0.0", "2.0.0", "1.2.3"), ("1.2.3", "1.2.3", None)],
)
def test_23_3_1_permits_repairs_to_unpublished_target_branch_versions(
    release: ReleaseFixture, base: str, current: str, published: str | None
) -> None:
    release.base_version(base)
    release.published_version(published)
    release.on("git diff", "packages/util/src/index.ts")
    release.write_json("packages/util/package.json", {"version": current})
    assert release.check_surface("origin/main") == [DONE]
    assert not release.matching("git diff")


@pytest.mark.parametrize(
    ("base", "baseline", "current", "published"),
    [
        ("1.2.4", "origin/main (1.2.4)", "1.2.5", "1.2.3"),
        ("1.2.4", "origin/main (1.2.4)", "1.3.0", "1.2.3"),
        ("1.2.3", "published 1.2.4", "1.2.5", "1.2.4"),
        ("1.2.3", "origin/main (1.2.3)", "1.2.4", None),
    ],
)
def test_23_3_2_uses_the_newer_published_or_target_branch_baseline(
    release: ReleaseFixture, base: str, baseline: str, current: str, published: str | None
) -> None:
    release.base_version(base)
    release.published_version(published)
    release.write_json("packages/util/package.json", {"version": current})
    assert release.check_surface("origin/main") == [
        {"message": f"@zyplux/util: {current} is ahead of {baseline}", "status": "pass"},
        DONE,
    ]


def test_23_3_3_rejects_regressions_against_an_unpublished_target_branch_version(release: ReleaseFixture) -> None:
    release.base_version("1.2.4")
    assert release.check_surface("origin/main") == [
        {"message": "@zyplux/util: version must not decrease from origin/main (1.2.4)", "status": "fail"}
    ]


def test_23_3_4_rejects_skipped_bumps_before_first_publication(release: ReleaseFixture) -> None:
    release.base_version("1.2.3")
    release.published_version()
    release.write_json("packages/util/package.json", {"version": "9.0.0"})
    assert release.check_surface("origin/main") == [
        {
            "message": "@zyplux/util: version 9.0.0 skips ahead of origin/main (1.2.3) — "
            "bump one step (1.2.4, 1.3.0, or 2.0.0)",
            "status": "fail",
        }
    ]


def test_23_3_5_allows_targets_introduced_by_the_pull_request(release: ReleaseFixture) -> None:
    release.base_version()
    release.published_version()
    assert release.check_surface("origin/main") == [
        {"message": "@zyplux/util: not yet released", "status": "pass"},
        DONE,
    ]


@pytest.mark.parametrize("manifest", ["invalid json", "{}", '{"version":"invalid"}'])
def test_23_3_6_rejects_malformed_target_branch_versions(release: ReleaseFixture, manifest: str) -> None:
    release.base_version("1.2.3")
    release.on("git show origin/main:packages/util/package.json", manifest)
    findings = release.check_surface("origin/main")
    assert findings[0]["status"] == "error"
    assert "cannot compare the target branch origin/main" in findings[0]["message"]


def test_23_3_7_rejects_unavailable_target_branch_history(release: ReleaseFixture) -> None:
    release.on("git ls-tree", Reply(exit_code=1))
    assert release.check_surface("origin/main")[0]["status"] == "error"


def test_23_3_8_reads_the_base_version_with_its_own_extractor_and_path(release: ReleaseFixture) -> None:
    release.base_version("1.2.3")
    release.configure("npm", 'version = { file = "packages/moved/package.json", json = "metadata.version" }')
    release.write_json("packages/moved/package.json", {"metadata": {"version": "1.2.4"}})
    assert release.check_surface("origin/main") == [
        {"message": "@zyplux/util: 1.2.4 is ahead of published 1.2.3", "status": "pass"},
        DONE,
    ]


def test_23_3_9_reports_missing_base_version_files(release: ReleaseFixture) -> None:
    release.base_version("1.2.3")
    release.on("git ls-tree --name-only origin/main -- packages/util/package.json")
    findings = release.check_surface("origin/main")
    assert findings[0]["status"] == "error"
    assert "version file packages/util/package.json is missing" in findings[0]["message"]


def test_23_3_10_distinguishes_targets_sharing_a_version_file(release: ReleaseFixture) -> None:
    release.base_version("9.0.0")
    release.on(
        "git show origin/main:airlock-targets.toml", release.read("airlock-targets.toml").replace("[util]", "[other]")
    )
    release.published_version()
    assert release.check_surface("origin/main") == [
        {"message": "@zyplux/util: not yet released", "status": "pass"},
        DONE,
    ]


def test_23_3_11_uses_the_github_target_branch_by_default(release: ReleaseFixture) -> None:
    release.env["GITHUB_BASE_REF"] = "main"
    release.base_version("1.2.4")
    assert release.check_surface() == [
        {"message": "@zyplux/util: version must not decrease from origin/main (1.2.4)", "status": "fail"}
    ]


@pytest.mark.parametrize(
    "config",
    [
        {"registry": "https://registry.npmjs.org/"},
        {"registry": "https://npm.pkg.github.com/"},
        {"@zyplux:registry": "https://npm.pkg.github.com/", "registry": "https://registry.npmjs.org"},
    ],
)
def test_23_4_1_follows_scoped_publication_registries(release: ReleaseFixture, config: dict[str, str]) -> None:
    release.env["NODE_AUTH_TOKEN"] = release.credential
    release.write_json("packages/util/package.json", {"publishConfig": config, "version": "1.2.3"})
    assert release.check_surface() == [DONE]
    registry = config.get("@zyplux:registry", config["registry"]).rstrip("/")
    assert any(
        request.url == f"{registry}/%40zyplux%2Futil" and request.method == "GET" for request in release.requests
    )


def test_23_4_2_rejects_missing_private_registry_credentials(release: ReleaseFixture) -> None:
    release.write_json(
        "packages/util/package.json", {"publishConfig": {"registry": "https://npm.pkg.github.com"}, "version": "1.2.3"}
    )
    findings = release.check_surface()
    assert findings[0]["status"] == "error"
    assert "GitHub Packages requires authentication" in findings[0]["message"]


@pytest.mark.parametrize("config", [{"registry": "https://example.com"}, {"registry": 42}, "invalid"])
def test_23_4_3_rejects_unsupported_publication_configuration(release: ReleaseFixture, config: object) -> None:
    release.write_json("packages/util/package.json", {"publishConfig": config, "version": "1.2.3"})
    assert release.check_surface()[0]["status"] == "error"


@pytest.mark.parametrize(
    ("metadata", "status"), [({}, 200), ({"dist-tags": {"latest": "invalid"}}, 200), ({}, 403), ({}, 502)]
)
def test_23_4_4_reports_registry_failures_as_errors(release: ReleaseFixture, metadata: object, status: int) -> None:
    release.serve("https://registry.npmjs.org/", Response(metadata, status))
    assert release.check_surface()[0]["status"] == "error"


def test_23_4_5_compares_stable_action_releases_across_all_pages(release: ReleaseFixture) -> None:
    release.configure("npm", 'kind = "action"\nrepository = "zyplux/zyplux"')
    release.write_json("packages/util/package.json", {"version": "1.10.1"})
    release.action_releases(
        [build_release("other-v99.0.0"), build_release("util-v1.9.0")],
        [
            build_release("util-v1.10.0"),
            build_release("util-v1.11.0", draft=True),
            build_release("util-v1.12.0", prerelease=True),
            build_release("util-v1.13.0-beta.1"),
            build_release("util-vinvalid"),
        ],
    )
    assert release.check_surface() == [
        {"message": "@zyplux/util: 1.10.1 is ahead of published 1.10.0", "status": "pass"},
        DONE,
    ]
    assert not release.matching("git ls-remote")


def test_23_4_6_selects_stable_numeric_container_tags(release: ReleaseFixture) -> None:
    release.configure("npm", 'kind = "ghcr"\nlabel = "ghcr.io/zyplux/ci"')
    release.serve("https://ghcr.io/v2/", Response({"tags": ["latest", "1.2.2", "1.2.4-beta.1"]}))
    assert release.check_surface() == [
        {"message": "ghcr.io/zyplux/ci: 1.2.3 is ahead of published 1.2.2", "status": "pass"},
        DONE,
    ]


def test_23_4_7_prints_readable_findings_without_json_mode(release: ReleaseFixture) -> None:
    assert release.run("check-surface").stdout.strip() == f"pass: {DONE['message']}"


@pytest.mark.parametrize("source", ["GH_TOKEN", "GITHUB_TOKEN", "gh login"])
def test_23_5_1_reads_private_npm_metadata_without_manual_node_auth_token_exports(
    release: ReleaseFixture, source: str
) -> None:
    if source == "gh login":
        release.on("gh auth token", "saved-token")
    else:
        release.env[source] = "saved-token"
    release.write_json(
        "packages/util/package.json", {"publishConfig": {"registry": "https://npm.pkg.github.com"}, "version": "1.2.3"}
    )
    assert release.check_surface() == [DONE]
    request = next(
        request for request in release.requests if request.url == "https://npm.pkg.github.com/%40zyplux%2Futil"
    )
    assert request.method == "GET"
    assert request.headers["authorization"] == "Bearer saved-token"
    if source != "gh login":
        assert not release.matching("gh auth token")


def test_23_5_2_authenticates_private_container_reads_with_the_saved_login_and_its_actor(
    release: ReleaseFixture,
) -> None:
    release.configure("npm", 'kind = "ghcr"\nlabel = "ghcr.io/zyplux/ci"')
    release.on("gh auth token", "saved-token")
    release.serve("https://api.github.com/user", Response({"login": "reader"}))
    assert release.check_surface() == [DONE]
    actor = next(request for request in release.requests if request.url == "https://api.github.com/user")
    assert actor.headers["authorization"] == "Bearer saved-token"
    assert actor.headers["user-agent"] == "zyplux-airlock"
    token = next(request for request in release.requests if request.url.startswith("https://ghcr.io/token"))
    assert token.headers["authorization"] == f"Basic {base64.b64encode(b'reader:saved-token').decode()}"


def test_23_5_3_preserves_explicitly_supplied_credentials_and_reports_denied_access(release: ReleaseFixture) -> None:
    release.env.update(NODE_AUTH_TOKEN=release.credential, GH_TOKEN=f"other-{release.credential}")
    release.on("gh auth token", "saved-token")
    release.write_json(
        "packages/util/package.json", {"publishConfig": {"registry": "https://npm.pkg.github.com"}, "version": "1.2.3"}
    )
    release.serve("https://npm.pkg.github.com/", Response(status=403))
    assert release.check_surface()[0]["status"] == "error"
    request = next(
        request for request in release.requests if request.url == "https://npm.pkg.github.com/%40zyplux%2Futil"
    )
    assert request.headers["authorization"] == f"Bearer {release.credential}"
    assert not release.matching("gh auth token")
