from __future__ import annotations

import hashlib
import json
import os
import stat
import tarfile
import zipfile
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
from airlock.targets import resolve_repo_path

if TYPE_CHECKING:
    from airlock.contracts import ReleaseTarget

type ContentEntry = tuple[str, bool, str]


def read_archive(archive: Path) -> list[ContentEntry]:
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as wheel:
            return [
                (
                    member.filename,
                    bool(member.external_attr >> 16 & stat.S_IXUSR),
                    hashlib.sha256(wheel.read(member)).hexdigest(),
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
            entries.append((path, bool(member.mode & stat.S_IXUSR), hashlib.sha256(stream.read()).hexdigest()))
    return entries


def calc_content_hash(archives: list[Path]) -> str:
    if not archives:
        msg = "package build produced no archives"
        raise ValueError(msg)
    entries = [
        (archive.suffix, path, executable, digest)
        for archive in archives
        for path, executable, digest in read_archive(archive)
    ]
    if any(path == "airlock-targets.toml" for _, path, _, _ in entries):
        msg = "package archives must exclude airlock-targets.toml to avoid a self-referential fingerprint"
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
    proc.run("uv", "build", "--package", target.spec.label, "--out-dir", str(directory), cwd=target.directory)
    return sorted(directory.glob("*.whl")) + sorted(directory.glob("*.tar.gz"))


def calc_source_hash(target: ReleaseTarget) -> str:
    root = proc.find_root(target.directory)
    directories = (
        {target.directory, target.action_directory or target.directory}
        if isinstance(target.spec, ActionSpec)
        else {target.build_context or target.directory}
    )
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
    entries = []
    if isinstance(target.spec, ActionSpec):
        for relative in target.spec.runtime_files:
            path = resolve_repo_path(root, relative)
            if not path.is_file():
                msg = f"{target.spec.label}: runtime file must exist: {relative}"
                raise ValueError(msg)
            files.update({root / relative, path})
    if target.spec.kind == "ghcr":
        context = target.build_context or target.directory
        dockerfile = target.dockerfile or next(
            (context / name for name in ("Containerfile", "Dockerfile") if (context / name).is_file()),
            context / "Containerfile",
        )
        if not dockerfile.is_file():
            msg = f"{target.spec.label}: Dockerfile must exist as a regular file: {dockerfile.relative_to(root)}"
            raise ValueError(msg)
        entries.extend([
            ("build_context", context.relative_to(root).as_posix(), False, ""),
            ("dockerfile", dockerfile.relative_to(root).as_posix(), False, ""),
        ])
        ignorefile = next(
            (context / name for name in (".containerignore", ".dockerignore") if (context / name).is_file()),
            None,
        )
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
            str(context), [".git", *patterns], dockerfile=dockerfile.relative_to(context, walk_up=True).as_posix()
        )
        files &= {context / path for path in included}
        files.add(dockerfile)
        if ignorefile is not None:
            files.add(ignorefile)
    # The manifest stores this fingerprint, so including it would make the hash depend on itself.
    files.discard(root / "airlock-targets.toml")
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
    if target.spec.content_hash is None:
        msg = f"{target.spec.label}: missing content_hash; run airlock prepare"
        raise ValueError(msg)
    if isinstance(target.spec, PackageSpec) and archives is None:
        with TemporaryDirectory(prefix="airlock-validate-") as directory:
            return validate_contents(target, build_archives(target, Path(directory)))
    fingerprint = calc_source_hash(target) if archives is None else calc_content_hash(archives)
    if fingerprint != target.spec.content_hash:
        msg = f"{target.spec.label}: release contents differ from content_hash; run airlock prepare"
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
        return calc_content_hash(archives), sorted(dependency.tag for dependency in load_dependencies(target, archives))


def update_content_hashes(targets: list[ReleaseTarget]) -> None:
    root = proc.find_root()
    hashes = {target.spec.tag_prefix.removesuffix("-v"): prepare_contents(target) for target in targets}
    if not hashes:
        return
    path = root / "airlock-targets.toml"
    manifest = tomlkit.parse(path.read_text(encoding="utf-8"))
    for name, declaration in manifest.items():
        if isinstance(declaration, Table) and name in hashes:
            fingerprint, dependencies = hashes[name]
            declaration["content_hash"] = fingerprint
            if dependencies is not None:
                declaration["requires"] = dependencies
            typer.echo(f"{name}: {fingerprint}")
    path.write_text(tomlkit.dumps(manifest), encoding="utf-8")
