from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from cli_fixture import Reply
from release_fixture import MISSING_RELEASE

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def test_21_1_1_plans_one_job_per_release_target(release: ReleaseFixture) -> None:
    assert release.plan() == [
        {"environment": "npm", "id": "npm-util", "kind": "npm", "runner": "ubuntu-latest", "tags": ["util-v1.2.3"]},
        {
            "environment": "pypi",
            "id": "pypi-cerberus",
            "kind": "pypi",
            "runner": "ubuntu-latest",
            "tags": ["cerberus-v2.3.4"],
        },
        {
            "environment": "ghcr",
            "id": "ghcr-ci-image",
            "kind": "ghcr",
            "runner": "ubuntu-latest",
            "tags": ["ci-image-v3.4.5"],
        },
    ]


def test_21_1_2_honors_target_environments(release: ReleaseFixture) -> None:
    release.configure("pypi", 'environment = "python-production"')
    batch = next(batch for batch in release.plan() if batch["kind"] == "pypi")
    assert batch["environment"] == "python-production"


def test_21_1_3_plans_action_alias_repair_independently(release: ReleaseFixture) -> None:
    release.action()
    assert release.plan() == [
        {
            "environment": "actions",
            "id": "action-setup-pm",
            "kind": "action",
            "runner": "ubuntu-latest",
            "tags": ["setup-pm-v1.0.0"],
        }
    ]


def test_21_2_1_publishes_only_the_selected_npm_target_and_writes_its_summary(release: ReleaseFixture) -> None:
    batch = release.plan()[0]
    release.env["GITHUB_STEP_SUMMARY"] = str(release.root / "summary.md")
    release.stage_npm()
    release.publish_batch(batch)
    release.expect_npm()
    assert not release.matching("uv|podman")
    assert "npm-util: published" in release.read("summary.md")
    assert "util-v1.2.3" in release.read("summary.md")


def test_21_2_2_honors_a_single_tag_plan_when_several_npm_targets_exist(release: ReleaseFixture) -> None:
    release.write(
        "airlock-targets.toml",
        release.read("airlock-targets.toml") + '\n[extra]\nkind = "npm"\nenvironment = "npm-extra"\nsurface = []\n'
        'version = { file = "packages/extra/package.json", json = "version" }\n',
    )
    release.write_json("packages/extra/package.json", {"name": "@zyplux/extra", "version": "1.2.3"})
    release.write("packages/extra/CHANGELOG.md", "# Extra\n\n## 1.2.3\n\n- Publish extra.\n")
    assert [batch["id"] for batch in release.plan() if batch["kind"] == "npm"] == ["npm-util", "npm-extra"]
    batch = release.plan("util-v1.2.3")[0]
    release.stage_npm()
    release.publish_batch(batch)
    assert len(release.matching("pnpm pack")) == 1
    assert not release.matching("gh release create extra-v")


def test_21_2_3_reports_a_failed_npm_batch_without_creating_github_releases(release: ReleaseFixture) -> None:
    batch = release.plan()[0]
    release.env["GITHUB_STEP_SUMMARY"] = str(release.root / "summary.md")
    release.stage_npm(exit_code=1)
    release.publish_batch(batch, error="command failed")
    assert "npm-util: failed" in release.read("summary.md")
    assert not release.matching("gh release create")


@pytest.mark.parametrize(
    "override",
    [
        {"environment": "wrong"},
        {"id": "wrong"},
        {"kind": "pypi"},
        {"tags": ["util-v0.0.1"]},
        {"tags": ["util-v1.2.3", "cerberus-v2.3.4"]},
    ],
)
def test_21_2_4_rejects_batches_that_disagree_with_the_checkout(
    release: ReleaseFixture, override: dict[str, object]
) -> None:
    batch = release.plan()[0]
    release.publish_batch({**batch, **override}, error="")
    assert not release.matching("pnpm publish|pnpm --filter|uv|podman")


def test_21_2_5_publishes_a_python_batch_through_uv(release: ReleaseFixture) -> None:
    batch = next(batch for batch in release.plan() if batch["kind"] == "pypi")
    release.on("uv build")
    release.on("uv publish")
    release.publish_batch(batch)
    assert release.matching("uv publish")
    assert release.matching("gh release create cerberus-v2.3.4")


def test_21_3_1_plans_no_batches_when_every_release_is_complete(release: ReleaseFixture) -> None:
    release.all_published()
    assert release.plan() == []


def test_21_3_2_retries_a_missing_artifact_whose_github_release_exists(release: ReleaseFixture) -> None:
    release.all_published(pypi=False)
    assert [batch["tags"] for batch in release.plan()] == [["cerberus-v2.3.4"]]


def test_21_3_3_selects_published_artifacts_with_missing_github_releases(release: ReleaseFixture) -> None:
    release.all_published()
    release.on(re.compile(r"tag=util-v1\.2\.3 "), MISSING_RELEASE)
    assert [batch["tags"] for batch in release.plan()] == [["util-v1.2.3"]]


def test_21_3_4_rejects_a_tag_that_does_not_match_a_configured_version(release: ReleaseFixture) -> None:
    release.plan("util-v1.2.2", error="no configured release target matches 'util-v1.2.2'")


def test_21_3_5_plans_no_batches_for_a_repository_with_no_release_targets(release: ReleaseFixture) -> None:
    release.write("airlock-targets.toml", 'scope = "@zyplux"\n')
    assert release.plan() == []


def test_21_3_6_propagates_release_lookup_failures_without_emitting_a_plan(release: ReleaseFixture) -> None:
    release.all_published()
    release.on("gh api graphql", Reply(stderr="authentication failed", exit_code=1))
    execution = release.run("plan", error="command failed")
    assert not execution.stdout
