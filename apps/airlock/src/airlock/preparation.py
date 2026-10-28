from __future__ import annotations

import json
import stat
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel

from airlock import github, proc
from airlock.contracts import VERSION_OBJECT, PackageIdentity
from airlock.registries import has_package_artifacts
from airlock.targets import build_release_target, parse_stable_version, resolve_repo_path

if TYPE_CHECKING:
    from collections.abc import Generator

    from airlock.contracts import ReleaseTarget

PREPARATION_FILE = ".changeset/preparation.json"
REGENERATED_FILES = {PREPARATION_FILE, "airlock_targets.toml", "pnpm-lock.yaml", "pnpm-workspace.yaml", "uv.lock"}
type MetadataSnapshot = dict[Path, tuple[bytes, int] | None]


class MetadataEdit(BaseModel):
    before: str | None
    after: str | None


class PreparedRelease(BaseModel):
    tags: list[str]
    files: dict[str, MetadataEdit]


def list_metadata(root: Path, targets: list[ReleaseTarget]) -> set[Path]:
    listing = proc.run("git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", str(root), cwd=root)
    directories = {
        root,
        *(target.directory for target in targets),
        *((root / name).parent for name in listing.split("\0") if Path(name).name == "package.json"),
    }
    return {
        *(directory / name for directory in directories for name in ("package.json", "pyproject.toml", "CHANGELOG.md")),
        *(resolve_repo_path(root, target.spec.manifest) for target in targets),
        *(path for path in (root / ".changeset").rglob("*") if path.is_file()),
        root / ".changeset/ledger.yaml",
        *(root / name for name in REGENERATED_FILES),
    }


def snapshot_metadata(paths: set[Path]) -> MetadataSnapshot:
    return {path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) if path.is_file() else None for path in paths}


def restore_metadata(snapshot: MetadataSnapshot) -> None:
    for path, saved in snapshot.items():
        if saved is None:
            path.unlink(missing_ok=True)
        else:
            contents, mode = saved
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
            path.chmod(mode)


def has_publication(target: ReleaseTarget, tags: set[str], root: Path) -> bool:
    if target.tag in tags:
        return True
    if target.spec.kind == "action":
        return bool(proc.run("git", "ls-remote", "origin", f"refs/tags/{target.tag}", cwd=root))
    return has_package_artifacts(target)


def validate_legacy_preparation(root: Path, targets: list[ReleaseTarget]) -> None:
    ledger = root / ".changeset/ledger.yaml"
    if not ledger.is_file() or not any(path.name != "README.md" for path in (root / ".changeset").glob("*.md")):
        return
    consumed = VERSION_OBJECT.validate_python(yaml.safe_load(ledger.read_text(encoding="utf-8")) or {})
    prepared = [target for target in targets if f"{target.package_name}@{target.version}" in consumed]
    if not prepared:
        return
    tags = {release.tag_name for release in github.fetch_release_history(directory=root)}
    for target in prepared:
        if not has_publication(target, tags, root):
            msg = (
                f"{target.tag}: pending release has no preparation record; finish its publication before "
                "adding more intents, or restore its baseline and original intents before preparing again"
            )
            raise ValueError(msg)


def rewind_json(current: dict[str, object], before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    missing = object()
    for key in before.keys() | after.keys():
        previous, prepared, observed = before.get(key, missing), after.get(key, missing), current.get(key, missing)
        if previous == prepared:
            continue
        if observed == prepared:
            if previous is missing:
                current.pop(key, None)
            else:
                current[key] = previous
        elif all(isinstance(item, dict) for item in (observed, previous, prepared)):
            current[key] = rewind_json(
                VERSION_OBJECT.validate_python(observed),
                VERSION_OBJECT.validate_python(previous),
                VERSION_OBJECT.validate_python(prepared),
            )
        else:
            msg = f"{key}: edits overlap prepared metadata"
            raise ValueError(msg)
    return current


def merge_metadata(current: str | None, edit: MetadataEdit, relative: str) -> str | None:
    if current in {edit.after, edit.before}:
        return edit.before
    if (
        relative == ".changeset/ledger.yaml"
        and current is not None
        and edit.after is not None
        and yaml.safe_load(current) == yaml.safe_load(edit.after)
    ):
        return edit.before
    if current is None or edit.before is None or edit.after is None:
        msg = f"{relative}: prepared metadata was edited; move release-note edits into a new pnpm change intent"
        raise ValueError(msg)
    if relative.endswith(".json"):
        return (
            json.dumps(
                rewind_json(*(VERSION_OBJECT.validate_json(text) for text in (current, edit.before, edit.after))),
                indent=2,
            )
            + "\n"
        )
    with TemporaryDirectory(prefix="airlock-merge-") as directory:
        paths = [Path(directory) / name for name in ("current", "prepared", "baseline")]
        for path, text in zip(paths, (current, edit.after, edit.before), strict=True):
            path.write_text(text, encoding="utf-8")
        try:
            return proc.run("git", "merge-file", "--stdout", *(str(path) for path in paths)) + "\n"
        except proc.CommandError as exc:
            msg = f"{relative}: edits overlap prepared metadata; preserve the edits as change intents before retrying"
            raise ValueError(msg) from exc


def rewind_preparation(root: Path, saved: PreparedRelease, targets: list[ReleaseTarget]) -> None:
    history = github.fetch_release_history(directory=root)
    tags = {release.tag_name for release in history}
    published = []
    for tag in saved.tags:
        target = next((target for target in targets if tag.startswith(target.spec.tag_prefix)), None)
        if target is None:
            msg = f"{tag}: prepared target is missing from airlock_targets.toml"
            raise ValueError(msg)
        release = build_release_target(
            root,
            target.spec,
            PackageIdentity(name=target.package_name, version=tag.removeprefix(target.spec.tag_prefix)),
        )
        releases = github.select_releases(history, target.spec.tag_prefix)
        if releases and releases[0][1] > parse_stable_version(release.version):
            msg = f"{tag}: a newer release is published; merge the latest target branch before preparing again"
            raise ValueError(msg)
        published.append(has_publication(release, tags, root))
    if published and all(published):
        return
    if any(published):
        msg = "Preparation has partially published releases; finish or retry publication before preparing more changes"
        raise ValueError(msg)
    restored = {}
    for relative, edit in saved.files.items():
        path = resolve_repo_path(root, relative)
        current = path.read_bytes().decode("utf-8") if path.is_file() else None
        restored[path] = merge_metadata(current, edit, relative)
    for path, text in restored.items():
        if text is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))


@contextmanager
def prepare_metadata(root: Path, targets: list[ReleaseTarget]) -> Generator[MetadataSnapshot]:
    path = root / PREPARATION_FILE
    saved = PreparedRelease.model_validate_json(path.read_bytes()) if path.is_file() else None
    paths = list_metadata(root, targets)
    if saved is not None:
        paths.update(resolve_repo_path(root, relative) for relative in saved.files)
    original = snapshot_metadata(paths)
    try:
        if saved is not None:
            rewind_preparation(root, saved, targets)
        else:
            validate_legacy_preparation(root, targets)
        yield snapshot_metadata(paths)
    except BaseException:
        for path in (root / ".changeset").rglob("*"):
            if path.is_file() and path not in original:
                path.unlink()
        restore_metadata(original)
        raise


def save_preparation(root: Path, baseline: MetadataSnapshot, targets: list[ReleaseTarget]) -> None:
    files = {}
    for path, original in baseline.items():
        relative = path.relative_to(root).as_posix()
        if relative in REGENERATED_FILES:
            continue
        before = original[0].decode("utf-8") if original is not None else None
        after = path.read_bytes().decode("utf-8") if path.is_file() else None
        if before != after:
            files[relative] = MetadataEdit(before=before, after=after)
    if not files:
        return
    tags = sorted(
        target.tag
        for target in targets
        if target.spec.manifest in files or (target.directory / "CHANGELOG.md").relative_to(root).as_posix() in files
    )
    saved = PreparedRelease(tags=tags, files=dict(sorted(files.items())))
    path = root / PREPARATION_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(saved.model_dump_json(indent=2) + "\n", encoding="utf-8")
