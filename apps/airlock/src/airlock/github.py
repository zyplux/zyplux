from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from airlock import proc
from airlock.contracts import GithubLookup, GithubRelease


def load_release(tag: str, *, assets: bool = False) -> GithubRelease | None:
    fields = "isDraft releaseAssets(first: 100) { nodes { name } }" if assets else "id"
    query = (
        "query($owner: String!, $name: String!, $tag: String!) { "
        "repository(owner: $owner, name: $name) { release(tagName: $tag) { " + fields + " } } }"
    )
    response = proc.run(
        "gh", "api", "graphql", "-F", "owner={owner}", "-F", "name={repo}", "-f", f"tag={tag}", "-f", f"query={query}"
    )
    return GithubLookup.model_validate_json(response).data.repository.release


def create_release(tag: str, notes: str, commit: str) -> None:
    with TemporaryDirectory(prefix="release-notes-") as directory:
        notes_file = Path(directory) / "release-notes.md"
        notes_file.write_text(f"{notes}\n", encoding="utf-8")
        proc.run("gh", "release", "create", tag, "--notes-file", str(notes_file), "--target", commit, "--title", tag)


def has_published_assets(release: GithubRelease | None, tag: str, assets: list[Path]) -> bool:
    if release is None or release.is_draft:
        return False
    if not {asset.name for asset in assets}.issubset(asset.name for asset in release.release_assets.nodes):
        msg = f"published release {tag} is missing required assets"
        raise ValueError(msg)
    return True


def publish_assets(tag: str, notes: str, commit: str, assets: list[Path]) -> None:
    release = load_release(tag, assets=True)
    if has_published_assets(release, tag, assets):
        return
    with TemporaryDirectory(prefix="release-assets-") as directory:
        notes_file = Path(directory) / "notes.md"
        notes_file.write_text(f"{notes}\n", encoding="utf-8")
        if release is None:
            proc.run(
                "gh",
                "release",
                "create",
                tag,
                "--draft",
                "--notes-file",
                str(notes_file),
                "--target",
                commit,
                "--title",
                tag,
            )
        if assets:
            proc.run("gh", "release", "upload", tag, *(str(asset) for asset in assets), "--clobber")
        proc.run("gh", "release", "edit", tag, "--draft=false", "--notes-file", str(notes_file), "--target", commit)
