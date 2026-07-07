from __future__ import annotations

import shutil
import subprocess
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from cerberus.context import Context
    from cerberus.model import Repo
    from cerberus.source import GitHistoryUnavailableError, LocalSource

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires the `git` binary on PATH")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def git_checkout(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "ci@zyplux.test")
    _git(tmp_path, "config", "user.name", "ci")
    return tmp_path


@pytest.fixture
def tagged_checkout(git_checkout: Path) -> Path:
    (git_checkout / "a.txt").write_text("one")
    _git(git_checkout, "add", "-A")
    _git(git_checkout, "commit", "-m", "first")
    _git(git_checkout, "tag", "widget-v0.1.0")
    _git(git_checkout, "tag", "other-v9.9.9")
    return git_checkout


@pytest.fixture
def diffable_checkout(git_checkout: Path) -> Path:
    (git_checkout / "tracked.txt").write_text("one")
    (git_checkout / "untouched.txt").write_text("stable")
    _git(git_checkout, "add", "-A")
    _git(git_checkout, "commit", "-m", "first")
    _git(git_checkout, "tag", "widget-v0.1.0")
    (git_checkout / "tracked.txt").write_text("two")
    _git(git_checkout, "add", "-A")
    _git(git_checkout, "commit", "-m", "second")
    return git_checkout


def test_17_1_1_names_the_repo_from_the_github_repository_environment_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, local_source: type[LocalSource], repo: Repo
) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "zyplux/widget")

    assert local_source(tmp_path).repos() == [replace(repo, name="widget")]


def test_17_1_2_falls_back_to_the_checkout_directory_name_when_the_env_var_is_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, local_source: type[LocalSource], repo: Repo
) -> None:
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    assert local_source(tmp_path).repos() == [replace(repo, name=tmp_path.resolve().name)]


def test_17_2_1_reads_the_content_of_a_file_at_a_given_path(tmp_path: Path, repo: Repo, local_source: type[LocalSource]) -> None:
    (tmp_path / "notes.txt").write_text("hello there")

    assert local_source(tmp_path).file(repo, "notes.txt") == "hello there"


def test_17_2_2_returns_nothing_for_a_path_that_does_not_exist(tmp_path: Path, repo: Repo, local_source: type[LocalSource]) -> None:
    assert local_source(tmp_path).file(repo, "missing.txt") is None


def test_17_2_3_writes_content_to_a_file_at_a_given_path(tmp_path: Path, repo: Repo, local_source: type[LocalSource]) -> None:
    src = local_source(tmp_path)

    src.write_file(repo, "notes.txt", "written content")

    assert (tmp_path / "notes.txt").read_text() == "written content"


@requires_git
def test_17_3_1_lists_tracked_files_and_skips_gitignored_paths(tmp_path: Path, repo: Repo, local_source: type[LocalSource]) -> None:
    _git(tmp_path, "init")
    (tmp_path / ".gitignore").write_text("reference_clones/\nnode_modules/\n")
    (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
    (tmp_path / "reference_clones").mkdir()
    (tmp_path / "reference_clones" / "vendor.test.ts").write_text("import 'bun:test';")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.ts").write_text("export const x = 1;")
    _git(tmp_path, "add", "-A")

    paths = local_source(tmp_path).list_paths(repo)

    assert paths == [".gitignore", "package.json"]


def test_17_3_2_falls_back_to_walking_the_filesystem_when_git_is_unavailable(tmp_path: Path, repo: Repo, local_source: type[LocalSource], no_git: None) -> None:
    del no_git
    (tmp_path / "a.txt").write_text("one")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "b.txt").write_text("two")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.ts").write_text("export const x = 1;")

    paths = local_source(tmp_path).list_paths(repo)

    assert paths == ["a.txt", "nested/b.txt"]


def test_17_4_1_lists_yaml_workflow_files_under_github_workflows_by_name(tmp_path: Path, repo: Repo, local_source: type[LocalSource]) -> None:
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "ci.yml").write_text("name: ci\n")
    (workflows_dir / "release.yaml").write_text("name: release\n")
    (workflows_dir / "README.md").write_text("not a workflow")

    workflows = local_source(tmp_path).workflows(repo)

    assert workflows == {"ci.yml": "name: ci\n", "release.yaml": "name: release\n"}


def test_17_4_2_returns_no_workflows_when_there_is_no_workflows_directory(tmp_path: Path, repo: Repo, local_source: type[LocalSource]) -> None:
    assert local_source(tmp_path).workflows(repo) == {}


@requires_git
def test_17_5_1_lists_tags_matching_a_given_prefix(tagged_checkout: Path, repo: Repo, local_source: type[LocalSource]) -> None:
    assert local_source(tagged_checkout).tags(repo, "widget-v") == ["widget-v0.1.0"]


@requires_git
def test_17_5_2_returns_no_tags_when_none_match_the_prefix(tagged_checkout: Path, repo: Repo, local_source: type[LocalSource]) -> None:
    assert local_source(tagged_checkout).tags(repo, "absent-v") == []


@requires_git
def test_17_6_1_lists_surface_paths_changed_since_the_ref(diffable_checkout: Path, repo: Repo, local_source: type[LocalSource]) -> None:
    changed = local_source(diffable_checkout).changed_paths(repo, "widget-v0.1.0", ["tracked.txt"])

    assert changed == ["tracked.txt"]


@requires_git
def test_17_6_2_excludes_surface_paths_unchanged_since_the_ref(diffable_checkout: Path, repo: Repo, local_source: type[LocalSource]) -> None:
    changed = local_source(diffable_checkout).changed_paths(repo, "widget-v0.1.0", ["untouched.txt"])

    assert changed == []


@requires_git
def test_17_7_1_errors_when_git_history_cannot_be_read_outside_a_repo(
    tmp_path: Path,
    repo: Repo,
    local_source: type[LocalSource],
    git_history_unavailable_error: type[GitHistoryUnavailableError],
) -> None:
    with pytest.raises(git_history_unavailable_error):
        local_source(tmp_path).tags(repo, "widget-v")


def test_17_7_2_errors_when_the_git_binary_is_missing(
    tmp_path: Path,
    repo: Repo,
    local_source: type[LocalSource],
    git_history_unavailable_error: type[GitHistoryUnavailableError],
    no_git: None,
) -> None:
    del no_git
    with pytest.raises(git_history_unavailable_error):
        local_source(tmp_path).tags(repo, "widget-v")


def test_17_8_1_serves_freshly_written_content_to_later_reads_in_the_same_run(tmp_path: Path, repo: Repo, make_context: Callable[..., Context]) -> None:
    (tmp_path / "doc.md").write_text("before")
    disk_ctx = make_context(tmp_path)
    assert disk_ctx.file(repo, "doc.md") == "before"

    disk_ctx.write_file(repo, "doc.md", "after")

    assert disk_ctx.file(repo, "doc.md") == "after"
    assert (tmp_path / "doc.md").read_text() == "after"


@requires_git
def test_17_8_2_keys_cached_history_reads_by_their_arguments(diffable_checkout: Path, repo: Repo, make_context: Callable[..., Context]) -> None:
    disk_ctx = make_context(diffable_checkout)

    assert disk_ctx.tags(repo, "widget-v") == ["widget-v0.1.0"]
    assert disk_ctx.tags(repo, "absent-v") == []
    assert disk_ctx.changed_paths(repo, "widget-v0.1.0", ["tracked.txt"]) == ["tracked.txt"]
    assert disk_ctx.changed_paths(repo, "widget-v0.1.0", ["untouched.txt"]) == []
