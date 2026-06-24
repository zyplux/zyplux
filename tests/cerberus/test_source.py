import shutil
import subprocess

import pytest
from cerberus import config, gh, source
from cerberus.model import Repo

requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="requires the `git` binary on PATH"
)


@pytest.fixture
def repo():
    return Repo("demo", "zyplux", "main", "public")


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@requires_git
def test_local_list_paths_returns_tracked_and_skips_gitignored(tmp_path, repo):
    _git(tmp_path, "init")
    (tmp_path / ".gitignore").write_text("reference_clones/\nnode_modules/\n")
    (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
    (tmp_path / "reference_clones").mkdir()
    (tmp_path / "reference_clones" / "vendor.test.ts").write_text("import 'bun:test';")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.ts").write_text("export const x = 1;")
    _git(tmp_path, "add", "-A")

    paths = source.LocalSource(tmp_path).list_paths(repo)

    assert "package.json" in paths
    assert ".gitignore" in paths
    assert not any("reference_clones" in path for path in paths)
    assert not any("node_modules" in path for path in paths)


@requires_git
def test_local_tags_lists_matching_prefix(tmp_path, repo):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "ci@zyplux.test")
    _git(tmp_path, "config", "user.name", "ci")
    (tmp_path / "a.txt").write_text("one")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "first")
    _git(tmp_path, "tag", "widget-v0.1.0")
    _git(tmp_path, "tag", "other-v9.9.9")

    src = source.LocalSource(tmp_path)

    assert src.tags(repo, "widget-v") == ["widget-v0.1.0"]
    assert src.tags(repo, "absent-v") == []


@requires_git
def test_local_changed_paths_diffs_surface_against_ref(tmp_path, repo):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "ci@zyplux.test")
    _git(tmp_path, "config", "user.name", "ci")
    (tmp_path / "tracked.txt").write_text("one")
    (tmp_path / "untouched.txt").write_text("stable")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "first")
    _git(tmp_path, "tag", "widget-v0.1.0")
    (tmp_path / "tracked.txt").write_text("two")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "second")

    src = source.LocalSource(tmp_path)

    assert src.changed_paths(repo, "widget-v0.1.0", ["tracked.txt"]) == ["tracked.txt"]
    assert src.changed_paths(repo, "widget-v0.1.0", ["untouched.txt"]) == []


@requires_git
def test_local_tags_raises_outside_a_repo(tmp_path, repo):
    with pytest.raises(source.GitHistoryUnavailable):
        source.LocalSource(tmp_path).tags(repo, "widget-v")


def test_github_list_paths_keeps_blobs_drops_trees(monkeypatch, repo):
    tree = {
        "tree": [
            {"path": "package.json", "type": "blob"},
            {"path": "src", "type": "tree"},
            {"path": "src/a.test.ts", "type": "blob"},
        ]
    }
    monkeypatch.setattr(gh, "api", lambda *_args, **_kwargs: tree)
    assert source.GitHubSource(config.load()).list_paths(repo) == [
        "package.json",
        "src/a.test.ts",
    ]
