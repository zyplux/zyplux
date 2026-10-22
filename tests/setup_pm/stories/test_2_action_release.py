from __future__ import annotations

import runpy
import subprocess
from typing import TYPE_CHECKING

import pytest
from setup_pm import publish

if TYPE_CHECKING:
    from pathlib import Path


def run_git(*args: str) -> str:
    return subprocess.run(("git", *args), check=True, text=True, capture_output=True).stdout.strip()


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    origin = tmp_path / "origin.git"
    run_git("init", "--bare", str(origin))
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    monkeypatch.chdir(checkout)
    run_git("init", "-b", "main")
    run_git("config", "user.name", "Action release test")
    run_git("config", "user.email", "action-test@example.com")
    run_git("remote", "add", "origin", str(origin))
    (checkout / "action.yml").write_text("name: First version\n")
    run_git("add", ".")
    run_git("commit", "-m", "First version")
    run_git("push", "-u", "origin", "main")
    return checkout


def test_2_1_1_creates_and_advances_v1_from_current_main(checkout: Path) -> None:
    runpy.run_path(publish.__file__, run_name="__main__")
    first_commit = run_git("rev-parse", "HEAD")
    assert run_git("ls-remote", "--refs", "origin", "refs/tags/v1").split()[0] == first_commit
    (checkout / "action.yml").write_text("name: Compatible update\n")
    run_git("commit", "-am", "Compatible update")
    run_git("push", "origin", "main")
    runpy.run_path(publish.__file__, run_name="__main__")
    latest_commit = run_git("rev-parse", "HEAD")
    assert latest_commit != first_commit
    assert run_git("ls-remote", "--refs", "origin", "refs/tags/v1").split()[0] == latest_commit


def test_2_2_1_skips_stale_successful_ci_commits(checkout: Path) -> None:
    first_commit = run_git("rev-parse", "HEAD")
    (checkout / "action.yml").write_text("name: New main\n")
    run_git("commit", "-am", "New main")
    run_git("push", "origin", "main", "HEAD:refs/tags/v1")
    latest_commit = run_git("rev-parse", "HEAD")
    run_git("checkout", "--detach", first_commit)
    runpy.run_path(publish.__file__, run_name="__main__")
    assert run_git("ls-remote", "--refs", "origin", "refs/tags/v1").split()[0] == latest_commit


@pytest.mark.usefixtures("checkout")
@pytest.mark.parametrize("has_newer_publication", [False, True])
def test_2_2_2_preserves_validated_releases_when_main_changes_during_publication(
    monkeypatch: pytest.MonkeyPatch, *, has_newer_publication: bool
) -> None:
    first_commit = run_git("rev-parse", "HEAD")
    next_commit = run_git("commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "Next main commit")
    publish_git = publish.run_git

    def advance_main(*args: str) -> str:
        stdout = publish_git(*args)
        if args == ("rev-parse", "FETCH_HEAD"):
            refs = [f"{next_commit}:refs/heads/main"]
            if has_newer_publication:
                refs.append(f"{next_commit}:refs/tags/v1")
            run_git("push", "origin", *refs)
        return stdout

    monkeypatch.setattr(publish, "run_git", advance_main)
    if has_newer_publication:
        with pytest.raises(subprocess.CalledProcessError):
            publish.main()
    else:
        publish.main()
    tag_commit = run_git("ls-remote", "--refs", "origin", "refs/tags/v1").split()[0]
    assert tag_commit == (next_commit if has_newer_publication else first_commit)
