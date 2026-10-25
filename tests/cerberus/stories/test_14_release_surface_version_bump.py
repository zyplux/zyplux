from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from archive_fixture import stage_packagers
from cli_fixture import Reply
from release_fixture import build_release
from release_surface_fixture import check_surface

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture
    from seam_fixtures import FakeProc, MakeFinding, RunCheckOnDisk, RunCheckWithFiles

DONE = {"message": "every published target's version tracks its contents", "status": "pass"}


@pytest.fixture
def release(release: ReleaseFixture) -> ReleaseFixture:
    release.use_package()
    stage_packagers(release)
    release.run("prepare")
    release.on(f"git -C {release.root} ls-tree --name-only util-v1.2.3 -- airlock-targets.toml", "airlock-targets.toml")
    release.on(f"git -C {release.root} show util-v1.2.3:airlock-targets.toml", release.read("airlock-targets.toml"))
    return release


@pytest.mark.parametrize("manifest", ["not = valid = toml", "", 'scope = ""', "scope = 1", 'scope = "@demo"\nutil = 1'])
def test_14_1_1_rejects_malformed_manifests(release: ReleaseFixture, manifest: str) -> None:
    release.write("airlock-targets.toml", manifest)
    assert [finding["status"] for finding in check_surface(release)] == ["error"]


def test_14_1_2_accepts_a_scope_with_no_targets(release: ReleaseFixture) -> None:
    release.write("airlock-targets.toml", 'scope = "@zyplux"')
    assert check_surface(release) == [DONE]


@pytest.mark.parametrize(
    "manifest", ["invalid json", "{}", '{"version":42}', '{"version":"invalid"}', '{"version":"1.2.3-beta.1"}']
)
def test_14_1_3_rejects_missing_or_invalid_versions(release: ReleaseFixture, manifest: str) -> None:
    release.write("packages/util/package.json", manifest)
    assert [finding["status"] for finding in check_surface(release)] == ["fail"]


def test_14_1_4_reports_missing_version_files(release: ReleaseFixture) -> None:
    release.configure("npm", 'version = { file = "missing.json", json = "version" }')
    findings = check_surface(release)
    assert findings[0]["status"] == "fail"
    assert "missing.json" in findings[0]["message"]


def test_14_1_5_reads_native_python_versions_with_the_configured_regex(release: ReleaseFixture) -> None:
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
    } in check_surface(release)


def test_14_1_6_validates_every_target_when_one_version_is_invalid(release: ReleaseFixture) -> None:
    release.write_json("packages/util/package.json", {"version": "1.2.4"})
    release.write(
        "airlock-targets.toml",
        release.read("airlock-targets.toml")
        + '\n[broken]\nkind = "npm"\nversion = { file = "missing.json", json = "version" }\n',
    )
    findings = check_surface(release)
    assert findings[0] == {"message": "@zyplux/util: 1.2.4 is ahead of published 1.2.3", "status": "pass"}
    assert findings[1]["status"] == "fail"
    assert "@zyplux/broken" in findings[1]["message"]


def test_14_1_7_reports_invalid_version_regexes(release: ReleaseFixture) -> None:
    release.configure("npm", 'version = { file = "packages/util/package.json", regex = "[" }')
    findings = check_surface(release)
    assert findings[0]["status"] == "fail"
    assert "packages/util/package.json: invalid version regex" in findings[0]["message"]


@pytest.mark.parametrize("version", ["1.2.4", "1.3.0", "2.0.0"])
def test_14_2_1_accepts_a_single_patch_minor_or_major_bump(release: ReleaseFixture, version: str) -> None:
    release.write_json("packages/util/package.json", {"version": version})
    assert check_surface(release) == [
        {"message": f"@zyplux/util: {version} is ahead of published 1.2.3", "status": "pass"},
        DONE,
    ]


@pytest.mark.parametrize("version", ["1.2.5", "1.4.0", "3.0.0", "1.3.1"])
def test_14_2_2_rejects_skipped_bumps(release: ReleaseFixture, version: str) -> None:
    release.write_json("packages/util/package.json", {"version": version})
    assert check_surface(release) == [
        {
            "message": f"@zyplux/util: version {version} skips ahead of published 1.2.3 — "
            "bump one step (1.2.4, 1.3.0, or 2.0.0)",
            "status": "fail",
        }
    ]


def test_14_2_3_rejects_versions_below_the_published_version(release: ReleaseFixture) -> None:
    release.published_version("1.10.0")
    assert check_surface(release) == [
        {"message": "@zyplux/util: version 1.2.3 is below published 1.10.0", "status": "fail"}
    ]


def test_14_2_4_permits_an_initial_release(release: ReleaseFixture) -> None:
    release.published_version()
    assert check_surface(release) == [{"message": "@zyplux/util: not yet released", "status": "pass"}, DONE]


def test_14_2_5_accepts_published_versions_with_unchanged_contents(release: ReleaseFixture) -> None:
    assert check_surface(release) == [DONE]


def test_14_2_6_rejects_changes_to_an_already_published_version(release: ReleaseFixture) -> None:
    release.write("packages/util/src/index.js", "changed contents")
    assert check_surface(release) == [
        {
            "message": "@zyplux/util: contents changed since util-v1.2.3 "
            "but version is still 1.2.3 — bump it (e.g. 1.2.4)",
            "status": "fail",
        }
    ]


def test_14_2_7_reports_unavailable_release_history(release: ReleaseFixture) -> None:
    release.on(f"git -C {release.root} show", Reply(exit_code=1))
    findings = check_surface(release)
    assert findings[0]["status"] == "error"
    assert "cannot compare contents against util-v1.2.3" in findings[0]["message"]


@pytest.mark.parametrize(
    ("base", "baseline", "current", "published"),
    [
        ("1.2.4", None, "1.2.4", "1.2.3"),
        ("2.0.0", None, "2.0.0", "1.2.3"),
        ("1.2.3", None, "1.2.3", None),
        ("1.2.4", "origin/main (1.2.4)", "1.2.5", "1.2.3"),
        ("1.2.4", "origin/main (1.2.4)", "1.3.0", "1.2.3"),
        ("1.2.3", "published 1.2.4", "1.2.5", "1.2.4"),
        ("1.2.3", "origin/main (1.2.3)", "1.2.4", None),
    ],
)
def test_14_3_1_compares_current_versions_against_the_latest_baseline(
    release: ReleaseFixture, base: str, baseline: str | None, current: str, published: str | None
) -> None:
    release.base_version(base)
    release.published_version(published)
    release.write_json("packages/util/package.json", {"version": current})
    expected: list[dict[str, str]] = (
        []
        if baseline is None
        else [
            {"message": f"@zyplux/util: {current} is ahead of {baseline}", "status": "pass"},
        ]
    )
    assert check_surface(release, "origin/main") == [*expected, DONE]


def test_14_3_3_rejects_regressions_against_an_unpublished_target_branch_version(release: ReleaseFixture) -> None:
    release.base_version("1.2.4")
    assert check_surface(release, "origin/main") == [
        {"message": "@zyplux/util: version must not decrease from origin/main (1.2.4)", "status": "fail"}
    ]


def test_14_3_4_rejects_skipped_bumps_before_first_publication(release: ReleaseFixture) -> None:
    release.base_version("1.2.3")
    release.published_version()
    release.write_json("packages/util/package.json", {"version": "9.0.0"})
    assert check_surface(release, "origin/main") == [
        {
            "message": "@zyplux/util: version 9.0.0 skips ahead of origin/main (1.2.3) — "
            "bump one step (1.2.4, 1.3.0, or 2.0.0)",
            "status": "fail",
        }
    ]


def test_14_3_5_allows_targets_introduced_by_the_pull_request(release: ReleaseFixture) -> None:
    release.base_version()
    release.published_version()
    assert check_surface(release, "origin/main") == [
        {"message": "@zyplux/util: not yet released", "status": "pass"},
        DONE,
    ]


@pytest.mark.parametrize("manifest", ["invalid json", "{}", '{"version":"invalid"}'])
def test_14_3_6_rejects_malformed_target_branch_versions(release: ReleaseFixture, manifest: str) -> None:
    release.base_version("1.2.3")
    release.on(f"git -C {release.root} show origin/main:packages/util/package.json", manifest)
    findings = check_surface(release, "origin/main")
    assert findings[0]["status"] == "error"
    assert "cannot compare the target branch origin/main" in findings[0]["message"]


def test_14_3_7_rejects_unavailable_target_branch_history(release: ReleaseFixture) -> None:
    release.on(f"git -C {release.root} ls-tree", Reply(exit_code=1))
    assert check_surface(release, "origin/main")[0]["status"] == "error"


def test_14_3_8_reads_the_base_version_with_its_own_extractor_and_path(release: ReleaseFixture) -> None:
    release.base_version("1.2.3")
    release.configure("npm", 'version = { file = "packages/moved/package.json", json = "metadata.version" }')
    release.write_json("packages/moved/package.json", {"metadata": {"version": "1.2.4"}})
    assert check_surface(release, "origin/main") == [
        {"message": "@zyplux/util: 1.2.4 is ahead of published 1.2.3", "status": "pass"},
        DONE,
    ]


def test_14_3_9_reports_missing_base_version_files(release: ReleaseFixture) -> None:
    release.base_version("1.2.3")
    release.on(f"git -C {release.root} ls-tree --name-only origin/main -- packages/util/package.json")
    findings = check_surface(release, "origin/main")
    assert findings[0]["status"] == "error"
    assert "version file packages/util/package.json is missing" in findings[0]["message"]


def test_14_3_10_distinguishes_targets_sharing_a_version_file(release: ReleaseFixture) -> None:
    release.base_version("9.0.0")
    release.on(
        f"git -C {release.root} show origin/main:airlock-targets.toml",
        release.read("airlock-targets.toml").replace("[util]", "[other]"),
    )
    release.published_version()
    assert check_surface(release, "origin/main") == [
        {"message": "@zyplux/util: not yet released", "status": "pass"},
        DONE,
    ]


def test_14_3_11_uses_the_github_target_branch_by_default(release: ReleaseFixture) -> None:
    release.env["GITHUB_BASE_REF"] = "main"
    release.base_version("1.2.4")
    assert check_surface(release) == [
        {"message": "@zyplux/util: version must not decrease from origin/main (1.2.4)", "status": "fail"}
    ]


def test_14_3_12_reads_a_shared_baseline_version_file_once(release: ReleaseFixture) -> None:
    release.write(
        "airlock-targets.toml",
        release.read("airlock-targets.toml") + '\n[other]\nkind = "npm"\n'
        'version = { file = "packages/util/package.json", json = "version" }\n',
    )
    release.base_version("1.2.3")
    release.write_json("packages/util/package.json", {"version": "1.2.4"})

    assert [finding["status"] for finding in check_surface(release, "origin/main")] == ["pass", "pass", "pass"]
    assert len(release.matching("git -C .* show origin/main:packages/util/package.json$")) == 1


@pytest.mark.parametrize("reply", [Reply(stdout="invalid"), Reply(stderr="Access denied", exit_code=1)])
def test_14_4_4_reports_release_history_failures_as_errors(release: ReleaseFixture, reply: Reply) -> None:
    release.on("gh api --paginate", reply)
    findings = check_surface(release)
    assert findings[0]["status"] == "error"
    assert "cannot check release contents" in findings[0]["message"]


def test_14_4_5_compares_stable_action_releases_across_all_pages(release: ReleaseFixture) -> None:
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
    assert check_surface(release) == [
        {"message": "@zyplux/util: 1.10.1 is ahead of published 1.10.0", "status": "pass"},
        DONE,
    ]
    assert not release.matching("git ls-remote")


def test_14_4_6_uses_successful_container_releases(release: ReleaseFixture) -> None:
    release.configure("npm", 'kind = "ghcr"\nlabel = "ghcr.io/zyplux/ci"')
    release.action_releases([build_release("util-v1.2.2"), build_release("util-v1.2.3", draft=True)])
    assert check_surface(release) == [
        {"message": "ghcr.io/zyplux/ci: 1.2.3 is ahead of published 1.2.2", "status": "pass"},
        DONE,
    ]
    assert not release.requests


def test_14_4_7_reads_release_history_once_for_all_targets(release: ReleaseFixture) -> None:
    release.write(
        "airlock-targets.toml",
        release.read("airlock-targets.toml") + '\n[other]\nkind = "npm"\n'
        'version = { file = "packages/other/package.json", json = "version" }\n',
    )
    release.write_json("packages/util/package.json", {"version": "1.2.4"})
    release.write_json("packages/other/package.json", {"version": "1.2.4"})
    release.action_releases([build_release("util-v1.2.3"), build_release("other-v1.2.3")])
    findings = check_surface(release)
    assert [finding["status"] for finding in findings] == ["pass", "pass", "pass"]
    assert findings[0]["message"].startswith("@zyplux/util:")
    assert findings[1]["message"].startswith("@zyplux/other:")
    assert len(release.matching("gh api --paginate")) == 1
    assert not release.requests


def test_14_4_8_rejects_action_repositories_outside_the_checkout(release: ReleaseFixture) -> None:
    release.configure("npm", 'kind = "action"\nrepository = "other/actions"')
    findings = check_surface(release)
    assert findings[0]["status"] == "error"
    assert "action repository other/actions must match checkout zyplux/zyplux" in findings[0]["message"]
    assert not release.matching("gh api --paginate")


CHECK_ID = "release_surface_version_bump"


def test_14_6_1_skips_repos_that_publish_nothing(
    run_check_with_files: RunCheckWithFiles, fake_proc: FakeProc, skip: MakeFinding
) -> None:
    result = run_check_with_files(CHECK_ID, {})
    assert result.findings == [skip("no airlock-targets.toml — repo publishes nothing")]
    assert fake_proc.calls == []


def test_14_6_2_checks_the_repository_without_an_npm_cli(
    run_check_on_disk: RunCheckOnDisk, fake_proc: FakeProc, ok: MakeFinding
) -> None:
    result = run_check_on_disk(CHECK_ID, {"airlock-targets.toml": 'scope = "@zyplux"'})
    assert result.findings == [ok(DONE["message"])]
    assert fake_proc.calls == []


@pytest.mark.parametrize("manifest", ["invalid = toml = text", "", 'scope = ""'])
def test_14_6_3_reports_manifest_errors(run_check_on_disk: RunCheckOnDisk, manifest: str) -> None:
    result = run_check_on_disk(CHECK_ID, {"airlock-targets.toml": manifest})
    assert len(result.problems) == 1
    assert result.problems[0].status.name == "ERROR"
    assert result.problems[0].message.startswith("cannot check release contents:")


def test_14_6_4_preserves_findings_from_multiple_targets(release: ReleaseFixture) -> None:
    release.write(
        "airlock-targets.toml",
        'scope = "@zyplux"\n'
        '[first]\nkind = "npm"\nversion = { file = "first.json", json = "version" }\n'
        '[second]\nkind = "npm"\nversion = { file = "second.json", json = "version" }\n',
    )
    findings = check_surface(release)
    assert [finding["status"] for finding in findings] == ["fail", "fail"]
    assert "@zyplux/first" in findings[0]["message"]
    assert "@zyplux/second" in findings[1]["message"]


def test_14_7_1_accepts_package_contents_matching_the_successful_release_tag(release: ReleaseFixture) -> None:
    assert check_surface(release) == [DONE]
    assert not release.requests
    assert not release.matching("git -C .* diff")
    assert release.matching("gh api --paginate")[0].cwd == str(release.root)


def test_14_7_2_detects_changes_even_after_the_pr_fingerprint_is_refreshed(release: ReleaseFixture) -> None:
    release.write("packages/util/src/index.js", "changed contents")
    release.run("prepare")
    findings = check_surface(release)
    assert findings[0]["status"] == "fail"
    assert "changed since util-v1.2.3" in findings[0]["message"]
    assert not release.requests


def test_14_7_3_uses_finalized_stable_releases_instead_of_registry_versions(release: ReleaseFixture) -> None:
    release.published_version("1.2.4")
    release.action_releases(
        [build_release("other-v9.0.0"), build_release("util-v1.2.4", draft=True)],
        [build_release("util-v2.0.0", prerelease=True), build_release("util-v1.2.3")],
    )
    assert check_surface(release) == [DONE]
    assert not release.requests


@pytest.mark.parametrize("has_manifest", [True, False])
def test_14_7_4_accepts_the_first_fingerprint_before_a_release_baseline_exists(
    release: ReleaseFixture, *, has_manifest: bool
) -> None:
    if has_manifest:
        release.on(
            f"git -C {release.root} show util-v1.2.3:airlock-targets.toml",
            'scope = "@zyplux"\n[util]\nkind = "npm"\nsurface = ["packages/util/src"]\n'
            'version = { file = "packages/util/package.json", json = "version" }\n',
        )
    else:
        release.on(f"git -C {release.root} ls-tree --name-only util-v1.2.3 -- airlock-targets.toml")
    assert check_surface(release) == [DONE]
    assert not release.matching("git -C .* diff")


def test_14_7_5_reports_package_build_failures(release: ReleaseFixture) -> None:
    release.on("pnpm pack", Reply(stderr="Packaging failed", exit_code=1))
    findings = check_surface(release)
    assert findings[0]["status"] == "error"
    assert "Packaging failed" in findings[0]["message"]


@pytest.mark.parametrize("kind", ["action", "ghcr"])
def test_14_7_6_requires_bumps_for_changed_action_and_container_inputs(release: ReleaseFixture, kind: str) -> None:
    fields = 'kind = "action"\nrepository = "zyplux/zyplux"' if kind == "action" else 'kind = "ghcr"'
    release.configure("npm", fields)
    release.write("packages/util/Containerfile", "FROM scratch\n")
    release.run("prepare")
    release.on(f"git -C {release.root} show util-v1.2.3:airlock-targets.toml", release.read("airlock-targets.toml"))
    release.write("packages/util/src/index.js", "changed source")
    release.run("prepare")
    findings = check_surface(release)
    assert findings[0]["status"] == "fail"
    assert "contents changed since util-v1.2.3" in findings[0]["message"]
