from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from archive_fixture import stage_packagers
from cli_fixture import Reply
from release_surface_fixture import check_readiness

if TYPE_CHECKING:
    from cli_fixture import Command
    from release_fixture import ReleaseFixture


def test_36_1_1_skips_repositories_without_release_targets(release: ReleaseFixture) -> None:
    (release.root / "airlock-targets.toml").unlink()
    assert check_readiness(release).status.name == "SKIP"
    assert not release.calls


def test_36_1_2_validates_the_selected_repository_without_changing_release_metadata(release: ReleaseFixture) -> None:
    stage_packagers(release)
    release.run("prepare")
    manifest = release.read("airlock-targets.toml")
    release.calls.clear()
    assert check_readiness(release).status.name == "PASS"
    assert release.read("airlock-targets.toml") == manifest
    assert not release.requests
    assert not release.matching(r"^gh\b|^(pnpm|uv) (version|install|lock|publish)\b")


@pytest.mark.parametrize("manifest", ["invalid = [", 'scope = "@demo"\nutil = 1'])
def test_36_1_3_rejects_malformed_release_manifests(release: ReleaseFixture, manifest: str) -> None:
    release.write("airlock-targets.toml", manifest)
    assert check_readiness(release).status.name == "FAIL"


@pytest.mark.parametrize("kind", ["npm", "pypi"])
def test_36_1_4_resolves_dependencies_inside_the_selected_repository_when_invoked_elsewhere(
    release: ReleaseFixture, kind: str
) -> None:
    if kind == "npm":
        release.consumer()
    else:
        release.configure("npm", 'kind = "pypi"\nlabel = "zyplux-util"')
        release.write("packages/util/pyproject.toml", '[project]\nname = "zyplux-util"\nversion = "1.2.3"\n')
        release.write(
            "apps/cerberus/pyproject.toml",
            release.read("apps/cerberus/pyproject.toml") + 'dependencies = ["zyplux-util>=1.0.0"]\n',
        )
    release.run("prepare")
    release.calls.clear()

    def find_root(call: Command) -> str:
        assert call.cwd is not None
        assert call.cwd.startswith(str(release.root) + "/")
        return str(release.root)

    release.on("git rev-parse --show-toplevel", find_root)
    assert check_readiness(release).status.name == "PASS"
    assert release.matching("git rev-parse --show-toplevel")
    assert not release.requests


def test_36_2_1_rejects_unconsumed_change_intents(release: ReleaseFixture) -> None:
    release.write(".changeset/pending.md", "Release notes awaiting preparation.\n")
    findings = check_readiness(release).problems
    assert len(findings) == 1
    assert "Unconsumed change intents: .changeset/pending.md" in findings[0].message


@pytest.mark.parametrize("override", [{"version": "2.3.5"}, {"name": "another-package"}, {"private": False}])
def test_36_2_2_rejects_inconsistent_python_tracking_manifests(
    release: ReleaseFixture, override: dict[str, object]
) -> None:
    release.write_json(
        "apps/cerberus/package.json", {"name": "zyplux-cerberus", "private": True, "version": "2.3.4", **override}
    )
    assert check_readiness(release).status.name == "FAIL"


@pytest.mark.parametrize("notes", ["## 1.2.2\n\n- Earlier release.\n", "## 1.2.3\n\n### Patch Changes\n"])
def test_36_2_3_rejects_missing_or_empty_current_release_notes(release: ReleaseFixture, notes: str) -> None:
    release.write("packages/util/CHANGELOG.md", notes)
    assert check_readiness(release).status.name == "FAIL"


@pytest.mark.parametrize("kind", ["npm", "pypi", "ghcr"])
def test_36_3_1_rejects_stale_fingerprints(release: ReleaseFixture, kind: str) -> None:
    stage_packagers(release)
    release.run("prepare")
    target = release.target({"npm": "util", "pypi": "cerberus", "ghcr": "ci"}[kind])
    (target.dir / "changed.py").write_text("changed")
    findings = check_readiness(release).problems
    assert len(findings) == 1
    reason = "build-input fingerprint differs" if kind == "ghcr" else "release contents differ"
    assert f"{reason} from content_hash; run airlock prepare" in findings[0].message


def test_36_3_2_reports_build_failures(release: ReleaseFixture) -> None:
    stage_packagers(release)
    release.run("prepare")
    release.on("pnpm pack", Reply(stderr="Packaging failed", exit_code=1))
    result = check_readiness(release)
    assert result.status.name == "ERROR"
    assert "Packaging failed" in result.problems[0].message


def test_36_3_3_rejects_missing_fingerprints(release: ReleaseFixture) -> None:
    result = check_readiness(release)
    assert result.status.name == "FAIL"
    assert "missing content_hash; run airlock prepare" in result.problems[0].message
    assert not release.matching("pnpm pack|uv build|publish")
