from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import ValidationError
from semantic_version import Version

from airlock import proc
from airlock.contracts import (
    STRING,
    TARGET_SPEC,
    VERSION_OBJECT,
    ContainerSpec,
    PackageIdentity,
    ReleaseTarget,
    TargetSpec,
)


def parse_stable_version(version: str) -> Version:
    try:
        parsed = Version(version)
    except ValueError as exc:
        msg = f"version '{version}' is not stable semver"
        raise ValueError(msg) from exc
    if parsed.prerelease:
        msg = f"version '{version}' is not stable semver"
        raise ValueError(msg)
    return parsed


def parse_target(name: str, settings: object, *, is_historical: bool) -> TargetSpec:
    declaration = VERSION_OBJECT.validate_python(settings)
    if is_historical:
        if "hash" not in declaration and "content_hash" in declaration:
            declaration["hash"] = declaration["content_hash"]
        if "manifest" not in declaration:
            source = VERSION_OBJECT.validate_python(declaration.get("version", {}))
            declaration["manifest"] = source.get("file")
        if declaration.get("kind") == "ghcr" and "package_name" not in declaration:
            declaration["package_name"] = declaration.get("label")
    if "kind" not in declaration:
        manifest = STRING.validate_python(declaration.get("manifest"))
        kind = {".json": "npm", ".toml": "pypi"}.get(Path(manifest).suffix)
        if kind is None:
            msg = f"{manifest}: cannot infer release kind from the manifest"
            raise ValueError(msg)
        declaration["kind"] = kind
    try:
        spec = TARGET_SPEC.validate_python(declaration, extra="ignore" if is_historical else "forbid")
    except ValidationError as exc:
        if any(error["type"] == "extra_forbidden" for error in exc.errors()):
            msg = f"Unrecognized key in {name}: {exc}"
            raise ValueError(msg) from exc
        raise
    return spec.model_copy(update={"name": name})


def parse_manifest(text: str, *, is_historical: bool = False) -> list[TargetSpec]:
    contents = tomllib.loads(text)
    if is_historical:
        contents.pop("scope", None)
    return [parse_target(name, settings, is_historical=is_historical) for name, settings in contents.items()]


def load_specs(root: Path) -> list[TargetSpec]:
    return parse_manifest((root / "airlock_targets.toml").read_text(encoding="utf-8"))


def parse_package(text: str, manifest: str) -> PackageIdentity:
    suffix = Path(manifest).suffix
    if suffix == ".json":
        contents = VERSION_OBJECT.validate_json(text)
    elif suffix == ".toml":
        contents = VERSION_OBJECT.validate_python(tomllib.loads(text)["project"])
    else:
        msg = f"{manifest}: manifest must be JSON or TOML"
        raise ValueError(msg)
    return PackageIdentity.model_validate(contents)


def resolve_repo_path(root: Path, relative: str) -> Path:
    resolved = (root / relative).resolve()
    if Path(relative).is_absolute() or not resolved.is_relative_to(root.resolve()):
        msg = f"release paths must be repository-relative: {relative}"
        raise ValueError(msg)
    return resolved


def resolve_container_paths(target: ReleaseTarget) -> tuple[Path, Path, Path | None]:
    context = target.build_context or target.directory
    dockerfile = target.dockerfile or next(
        (context / name for name in ("Containerfile", "Dockerfile") if (context / name).is_file()),
        context / "Containerfile",
    )
    if not dockerfile.is_file():
        msg = (
            f"{target.package_name}: Dockerfile must exist as a regular file: "
            f"{dockerfile.relative_to(proc.find_root(target.directory))}"
        )
        raise ValueError(msg)
    ignorefile = next(
        (
            directory / name
            for directory in (dockerfile.parent, context)
            for name in (".containerignore", ".dockerignore")
            if (directory / name).is_file()
        ),
        None,
    )
    return context, dockerfile, ignorefile


def build_release_target(root: Path, spec: TargetSpec, package: PackageIdentity) -> ReleaseTarget:
    directory = resolve_repo_path(root, spec.manifest).parent
    build_context = None
    dockerfile = None
    if isinstance(spec, ContainerSpec):
        build_context = resolve_repo_path(root, spec.build_context or str(Path(spec.manifest).parent))
        dockerfile = None if spec.dockerfile is None else resolve_repo_path(root, spec.dockerfile)
    return ReleaseTarget(spec, spec.package_name or package.name, package.version, directory, build_context, dockerfile)


def load_targets(root: Path | None = None) -> list[ReleaseTarget]:
    root = root or proc.find_root()
    return [
        build_release_target(
            root,
            spec,
            parse_package(resolve_repo_path(root, spec.manifest).read_text(encoding="utf-8"), spec.manifest),
        )
        for spec in load_specs(root)
    ]
