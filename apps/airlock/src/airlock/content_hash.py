from __future__ import annotations

import hashlib
import json
import os
import stat
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from urllib.parse import quote

import tomlkit
import typer
from docker.utils import exclude_paths
from tomlkit.items import Table

from airlock import proc
from airlock.contracts import ActionSpec, PackageSpec
from airlock.dependencies import load_dependencies, validate_dependency_cycles, validate_prepared_dependencies
from airlock.targets import resolve_container_paths, resolve_repo_path

if TYPE_CHECKING:
    from airlock.contracts import ReleaseTarget

type ArchiveEntry = tuple[str, bool, bytes]


def read_archive(archive: Path) -> list[ArchiveEntry]:
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as wheel:
            return [
                (
                    member.filename,
                    bool(member.external_attr >> 16 & stat.S_IXUSR),
                    wheel.read(member),
                )
                for member in wheel.infolist()
                if not member.is_dir()
            ]
    entries = []
    with tarfile.open(archive) as package:
        for member in package:
            if member.isdir():
                continue
            stream = package.extractfile(member)
            if stream is None or not member.isfile():
                msg = f"{archive.name}: unsupported package entry {member.name}"
                raise ValueError(msg)
            path = "/".join(PurePosixPath(member.name).parts[1:])
            entries.append((path, bool(member.mode & stat.S_IXUSR), stream.read()))
    return entries


def is_included(path: str, includes: list[str]) -> bool:
    relative = PurePosixPath(path)
    return any(relative.full_match(glob) for glob in includes if not glob.startswith("!")) and not any(
        relative.full_match(glob[1:]) for glob in includes if glob.startswith("!")
    )


def has_excluded_readme(target: ReleaseTarget) -> bool:
    if target.spec.kind != "pypi":
        return False
    project = tomllib.loads((target.directory / "pyproject.toml").read_text(encoding="utf-8")).get("project", {})
    readme = project.get("readme")
    filename = readme.get("file") if isinstance(readme, dict) else readme
    return isinstance(filename, str) and not is_included(filename, target.spec.includes)


def normalize_metadata(path: str, contents: bytes, *, exclude_readme: bool) -> bytes:
    if exclude_readme and (path.endswith(".dist-info/METADATA") or PurePosixPath(path).name == "PKG-INFO"):
        metadata = BytesParser().parsebytes(contents)
        del metadata["Description"]
        del metadata["Description-Content-Type"]
        metadata.set_payload("")
        return metadata.as_bytes()
    return contents


def calc_content_hash(archives: list[Path], target: ReleaseTarget) -> str:
    if not archives:
        msg = "package build produced no archives"
        raise ValueError(msg)
    exclude_readme = has_excluded_readme(target)
    entries = [
        (
            archive.suffix,
            path,
            executable,
            hashlib.sha256(normalize_metadata(path, contents, exclude_readme=exclude_readme)).hexdigest(),
        )
        for archive in archives
        for path, executable, contents in read_archive(archive)
        if is_included(path, target.spec.includes) and not path.endswith(".dist-info/RECORD")
    ]
    if any(path == "airlock_targets.toml" for _, path, _, _ in entries):
        msg = "package archives must exclude airlock_targets.toml to avoid a self-referential fingerprint"
        raise ValueError(msg)
    return calc_entries_hash(entries)


def calc_entries_hash(entries: list[tuple[str, str, bool, str]]) -> str:
    digest = hashlib.sha256(json.dumps(sorted(entries), separators=(",", ":")).encode()).hexdigest()
    return f"sha256:{digest}"


def build_archives(target: ReleaseTarget, directory: Path) -> list[Path]:
    if target.spec.kind == "npm":
        archive = directory / f"{quote(target.tag, safe='')}.tgz"
        proc.run("pnpm", "pack", "--out", str(archive), cwd=target.directory)
        return [archive]
    proc.run("uv", "build", "--package", target.package_name, "--out-dir", str(directory), cwd=target.directory)
    return sorted(directory.glob("*.whl")) + sorted(directory.glob("*.tar.gz"))


def calc_source_hash(target: ReleaseTarget) -> str:
    root = proc.find_root(target.directory)
    entries = []
    if target.spec.kind == "ghcr":
        context, dockerfile, ignorefile = resolve_container_paths(target)
        entries.extend([
            ("build_context", context.relative_to(root).as_posix(), False, ""),
            ("dockerfile", dockerfile.relative_to(root).as_posix(), False, ""),
        ])
        patterns = (
            []
            if ignorefile is None
            else [
                line.strip()
                for line in ignorefile.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            ]
        )
        included = exclude_paths(
            str(context), patterns, dockerfile=dockerfile.relative_to(context, walk_up=True).as_posix()
        )
        if any(".git" in Path(path).parts for path in included):
            msg = (
                f"{target.package_name}: container build context includes Git metadata; "
                "exclude .git in the container ignore file"
            )
            raise ValueError(msg)
        files = {context / path for path in included}
        files.add(dockerfile)
        if ignorefile is not None:
            files.add(ignorefile)
    else:
        directories = {target.directory, target.action_directory or target.directory}
        listing = proc.run(
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            *(str(directory) for directory in sorted(directories)),
            cwd=root,
        )
        files = {root / path for path in listing.split("\0") if path}
        if isinstance(target.spec, ActionSpec):
            for relative in target.spec.runtime_files:
                path = resolve_repo_path(root, relative)
                if not path.is_file():
                    msg = f"{target.package_name}: runtime file must exist: {relative}"
                    raise ValueError(msg)
                files.update({root / relative, path})
    # The manifest stores this fingerprint, so including it would make the hash depend on itself.
    files.discard(root / "airlock_targets.toml")
    files = {
        path
        for path in files
        if is_included(path.relative_to(target.directory, walk_up=True).as_posix(), target.spec.includes)
    }
    for path in files:
        if path.is_symlink():
            kind, contents = "symlinks", os.fsencode(path.readlink())
        elif path.is_file():
            kind, contents = "files", path.read_bytes()
        else:
            continue
        entries.append((
            kind,
            path.relative_to(root).as_posix(),
            bool(path.lstat().st_mode & stat.S_IXUSR),
            hashlib.sha256(contents).hexdigest(),
        ))
    return calc_entries_hash(entries)


def validate_contents(target: ReleaseTarget, archives: list[Path] | None = None) -> list[ReleaseTarget]:
    if target.spec.hash is None:
        msg = f"{target.package_name}: missing hash; run airlock prepare"
        raise ValueError(msg)
    if isinstance(target.spec, PackageSpec) and archives is None:
        with TemporaryDirectory(prefix="airlock-validate-") as directory:
            return validate_contents(target, build_archives(target, Path(directory)))
    fingerprint = calc_source_hash(target) if archives is None else calc_content_hash(archives, target)
    if fingerprint != target.spec.hash:
        msg = f"{target.package_name}: release contents differ from hash; run airlock prepare"
        if target.spec.kind == "ghcr":
            root = proc.find_root(target.directory)
            context, dockerfile, ignorefile = resolve_container_paths(target)
            msg = (
                f"{target.package_name}: build-input fingerprint differs from hash; run airlock prepare\n"
                f"build context: {context.relative_to(root)}\n"
                f"Dockerfile: {dockerfile.relative_to(root)}\n"
                f"ignore file: {ignorefile.relative_to(root) if ignorefile is not None else 'none'}"
            )
        raise ValueError(msg)
    if archives is None:
        return []
    dependencies = load_dependencies(target, archives)
    validate_prepared_dependencies(target, dependencies)
    validate_dependency_cycles(target, dependencies)
    return dependencies


def prepare_contents(target: ReleaseTarget) -> tuple[str, list[str] | None]:
    if not isinstance(target.spec, PackageSpec):
        return calc_source_hash(target), None
    with TemporaryDirectory(prefix="airlock-prepare-") as directory:
        archives = build_archives(target, Path(directory))
        return calc_content_hash(archives, target), sorted(
            dependency.spec.name for dependency in load_dependencies(target, archives)
        )


def update_content_hashes(targets: list[ReleaseTarget]) -> None:
    root = proc.find_root()
    hashes = {target.spec.name: prepare_contents(target) for target in targets}
    if not hashes:
        return
    path = root / "airlock_targets.toml"
    manifest = tomlkit.parse(path.read_text(encoding="utf-8"))
    for name, declaration in manifest.items():
        if isinstance(declaration, Table) and name in hashes:
            fingerprint, dependencies = hashes[name]
            declaration["hash"] = fingerprint
            if dependencies:
                declaration["depends_on"] = dependencies
            else:
                declaration.pop("depends_on", None)
            typer.echo(f"{name}: {fingerprint}")
    path.write_text(tomlkit.dumps(manifest), encoding="utf-8")
