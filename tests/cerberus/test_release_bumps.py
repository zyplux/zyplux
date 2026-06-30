from pathlib import Path

import pytest
from cerberus import config, context
from cerberus.checks import release_bumps_check
from cerberus.model import Repo, Status

MANIFEST = """
[[target]]
kind = "npm"
label = "@zyplux/widget"
tag_prefix = "widget-v"
version = { file = "packages/widget/package.json", json = "version" }
surface = ["packages/widget/src"]
"""

VERSION_FILE = "packages/widget/package.json"


@pytest.fixture
def repo() -> Repo:
    return Repo("demo")


@pytest.fixture
def ctx() -> context.Context:
    return context.local_context(config.load(), Path())


def _wire(
    monkeypatch: pytest.MonkeyPatch, ctx: context.Context, *, version: str | None, tags: list[str], changed: list[str]
) -> None:
    files = {"release-targets.toml": MANIFEST}
    if version is not None:
        files[VERSION_FILE] = f'{{"version": "{version}"}}'
    monkeypatch.setattr(ctx, "file", lambda _r, path: files.get(path))
    monkeypatch.setattr(ctx, "tags", lambda *_: tags)
    monkeypatch.setattr(ctx, "changed_paths", lambda *_: changed)


def test_skips_when_no_manifest(monkeypatch: pytest.MonkeyPatch, repo: Repo, ctx: context.Context) -> None:
    monkeypatch.setattr(ctx, "file", lambda *_: None)
    assert release_bumps_check.run(repo, ctx).status is Status.SKIP


def test_passes_when_version_ahead_of_latest_tag(
    monkeypatch: pytest.MonkeyPatch, repo: Repo, ctx: context.Context
) -> None:
    _wire(monkeypatch, ctx, version="0.2.0", tags=["widget-v0.1.0"], changed=[])
    assert release_bumps_check.run(repo, ctx).status is Status.PASS


def test_passes_when_not_yet_released(monkeypatch: pytest.MonkeyPatch, repo: Repo, ctx: context.Context) -> None:
    _wire(monkeypatch, ctx, version="0.1.0", tags=[], changed=["packages/widget/src/a.ts"])
    assert release_bumps_check.run(repo, ctx).status is Status.PASS


def test_fails_when_version_below_published(monkeypatch: pytest.MonkeyPatch, repo: Repo, ctx: context.Context) -> None:
    _wire(monkeypatch, ctx, version="0.1.0", tags=["widget-v0.2.0"], changed=[])
    assert release_bumps_check.run(repo, ctx).status is Status.FAIL


def test_passes_when_surface_unchanged_since_tag(
    monkeypatch: pytest.MonkeyPatch, repo: Repo, ctx: context.Context
) -> None:
    _wire(monkeypatch, ctx, version="0.1.0", tags=["widget-v0.1.0"], changed=[])
    assert release_bumps_check.run(repo, ctx).status is Status.PASS


def test_fails_when_surface_changed_without_bump(
    monkeypatch: pytest.MonkeyPatch, repo: Repo, ctx: context.Context
) -> None:
    _wire(
        monkeypatch,
        ctx,
        version="0.1.0",
        tags=["widget-v0.1.0"],
        changed=["packages/widget/src/a.ts"],
    )
    result = release_bumps_check.run(repo, ctx)
    assert result.status is Status.FAIL
    assert any("bump it" in finding.message for finding in result.problems)


def test_picks_highest_tag_not_newest_listed(monkeypatch: pytest.MonkeyPatch, repo: Repo, ctx: context.Context) -> None:
    _wire(monkeypatch, ctx, version="0.2.0", tags=["widget-v0.2.0", "widget-v0.10.0"], changed=[])
    result = release_bumps_check.run(repo, ctx)
    assert result.status is Status.FAIL
    assert any("0.10.0" in finding.message for finding in result.problems)


def test_errors_when_manifest_malformed(monkeypatch: pytest.MonkeyPatch, repo: Repo, ctx: context.Context) -> None:
    monkeypatch.setattr(ctx, "file", lambda *_: "not = valid = toml")
    assert release_bumps_check.run(repo, ctx).status is Status.ERROR
