from __future__ import annotations

import json
import re
import stat
import tomllib
from collections.abc import MutableMapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, cast

import tomlkit
import yaml
from markdown_it import MarkdownIt
from pydantic import BaseModel, Field

from airlock import github, proc
from airlock.contracts import VERSION_OBJECT, PackageIdentity
from airlock.registries import has_package_artifacts
from airlock.targets import build_release_target, parse_stable_version, resolve_repo_path

if TYPE_CHECKING:
    from collections.abc import Generator

    from airlock.contracts import ReleaseTarget

PREPARATION_FORMAT = 2
PREPARATION_FILE = ".changeset/preparation.json"
REGENERATED_FILES = {PREPARATION_FILE, "airlock_targets.toml", "pnpm-lock.yaml", "pnpm-workspace.yaml", "uv.lock"}
type MetadataSnapshot = dict[Path, tuple[bytes, int] | None]


class MetadataEdit(BaseModel):
    before: dict[str, object]
    after: dict[str, object]
    created: bool = False


class PreparedRelease(BaseModel):
    format: int = PREPARATION_FORMAT
    tags: list[str]
    intents: dict[str, str] = Field(default_factory=dict)
    files: dict[str, MetadataEdit] = Field(default_factory=dict)


class FileSnapshot(BaseModel):
    before: str | None
    after: str | None


class LegacyPreparation(BaseModel):
    tags: list[str]
    files: dict[str, FileSnapshot]


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


def parse_changelog(text: str) -> dict[str, object]:
    lines = text.splitlines(keepends=True)
    headings = [
        token.map[0]
        for token in MarkdownIt().parse(text)
        if token.type == "heading_open" and token.tag == "h2" and token.level == 0 and token.map
    ]
    sections: dict[str, object] = {}
    if lines[: headings[0] if headings else len(lines)]:
        sections[""] = "".join(lines[: headings[0] if headings else len(lines)])
    for start, end in zip(headings, [*headings[1:], len(lines)], strict=True):
        heading = lines[start].strip()
        if heading in sections:
            msg = f"{heading}: duplicate changelog section"
            raise ValueError(msg)
        sections[heading] = "".join(lines[start:end])
    return sections


def parse_metadata(text: str | None, relative: str) -> dict[str, object]:
    if text is None:
        return {}
    if relative.endswith(".json"):
        return VERSION_OBJECT.validate_json(text)
    if relative.endswith(".toml"):
        return tomllib.loads(text)
    if relative == ".changeset/ledger.yaml":
        return VERSION_OBJECT.validate_python(yaml.safe_load(text) or {})
    if relative.endswith("/CHANGELOG.md") or relative == "CHANGELOG.md":
        return parse_changelog(text)
    msg = f"{relative}: unsupported prepared metadata"
    raise ValueError(msg)


def select_edits(before: dict[str, object], after: dict[str, object]) -> MetadataEdit:
    previous: dict[str, object] = {}
    prepared: dict[str, object] = {}
    for key in sorted(before.keys() | after.keys()):
        if key in before and key in after and before[key] == after[key]:
            continue
        if isinstance(before.get(key), dict) and isinstance(after.get(key), dict):
            nested = select_edits(
                VERSION_OBJECT.validate_python(before[key]), VERSION_OBJECT.validate_python(after[key])
            )
            previous[key], prepared[key] = nested.before, nested.after
        else:
            if key in before:
                previous[key] = before[key]
            if key in after:
                prepared[key] = after[key]
    return MetadataEdit(before=previous, after=prepared)


def build_preparation(tags: list[str], files: dict[str, FileSnapshot]) -> PreparedRelease:
    saved = PreparedRelease(tags=tags)
    for relative, edit in sorted(files.items()):
        if (
            relative.startswith(".changeset/")
            and relative.endswith(".md")
            and edit.before is not None
            and edit.after is None
        ):
            saved.intents[relative] = edit.before
            continue
        selected = select_edits(parse_metadata(edit.before, relative), parse_metadata(edit.after, relative))
        if selected.before or selected.after:
            selected.created = edit.before is None
            saved.files[relative] = selected
    return saved


def load_preparation(path: Path) -> PreparedRelease:
    record = VERSION_OBJECT.validate_json(path.read_bytes())
    if "format" not in record:
        legacy = LegacyPreparation.model_validate(record)
        return build_preparation(legacy.tags, legacy.files)
    if record["format"] != PREPARATION_FORMAT:
        msg = f"{path}: unsupported preparation format {record['format']}"
        raise ValueError(msg)
    return PreparedRelease.model_validate(record)


def rewind_fields(current: MutableMapping[str, object], before: dict[str, object], after: dict[str, object]) -> None:
    missing = object()
    for key in before.keys() | after.keys():
        previous, prepared, observed = before.get(key, missing), after.get(key, missing), current.get(key, missing)
        if (
            isinstance(prepared, dict)
            and (isinstance(previous, dict) or previous is missing)
            and isinstance(observed, MutableMapping)
        ):
            rewind_fields(
                observed, VERSION_OBJECT.validate_python(previous) if previous is not missing else {}, prepared
            )
            if previous is missing and not observed:
                del current[key]
        elif observed == prepared:
            if previous is missing:
                current.pop(key, None)
            else:
                current[key] = previous
        else:
            msg = f"{key}: edits overlap prepared metadata"
            raise ValueError(msg)


def merge_metadata(current: str | None, edit: MetadataEdit, relative: str) -> str | None:
    if current is None:
        msg = f"{relative}: prepared metadata is missing"
        raise ValueError(msg)
    if relative.endswith(".toml"):
        document = tomlkit.parse(current)
        rewind_fields(cast("MutableMapping[str, object]", document), edit.before, edit.after)
        return None if edit.created and not document else tomlkit.dumps(document)
    fields = parse_metadata(current, relative)
    rewind_fields(fields, edit.before, edit.after)
    if edit.created and not fields:
        return None
    if relative.endswith(".json"):
        indentation = re.search(r'^([ \t]+)"', current, re.MULTILINE)
        indent = indentation[1] if indentation else None
        separators = None if indent else ((", ", ": ") if '": ' in current else (",", ":"))
        return json.dumps(fields, indent=indent, separators=separators) + ("\n" if current.endswith("\n") else "")
    if relative == ".changeset/ledger.yaml":
        return yaml.safe_dump(fields, sort_keys=True)
    return "".join(str(section) for section in fields.values())


def is_preparation_published(root: Path, saved: PreparedRelease, targets: list[ReleaseTarget]) -> bool:
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
        return True
    if any(published):
        msg = "Preparation has partially published releases; finish or retry publication before preparing more changes"
        raise ValueError(msg)
    return False


def rewind_preparation(root: Path, saved: PreparedRelease, targets: list[ReleaseTarget]) -> None:
    if is_preparation_published(root, saved, targets):
        (root / PREPARATION_FILE).unlink(missing_ok=True)
        return
    restored = {}
    for relative, edit in saved.files.items():
        path = resolve_repo_path(root, relative)
        current = path.read_bytes().decode("utf-8") if path.is_file() else None
        restored[path] = merge_metadata(current, edit, relative)
    for relative, text in saved.intents.items():
        path = resolve_repo_path(root, relative)
        if path.exists() and path.read_text(encoding="utf-8") != text:
            msg = f"{relative}: edits overlap prepared metadata"
            raise ValueError(msg)
        restored[path] = text
    for path, text in restored.items():
        if text is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
    (root / PREPARATION_FILE).unlink(missing_ok=True)


@contextmanager
def prepare_metadata(root: Path, targets: list[ReleaseTarget]) -> Generator[MetadataSnapshot]:
    path = root / PREPARATION_FILE
    saved = load_preparation(path) if path.is_file() else None
    paths = list_metadata(root, targets)
    if saved is not None:
        paths.update(resolve_repo_path(root, relative) for relative in saved.files.keys() | saved.intents.keys())
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
            files[relative] = FileSnapshot(before=before, after=after)
    saved = build_preparation([], files)
    saved.tags = sorted(
        target.tag
        for target in targets
        if target.spec.manifest in saved.files
        or (target.directory / "CHANGELOG.md").relative_to(root).as_posix() in saved.files
    )
    path = root / PREPARATION_FILE
    if not saved.files and not saved.intents:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(saved.model_dump_json(indent=2) + "\n", encoding="utf-8")
