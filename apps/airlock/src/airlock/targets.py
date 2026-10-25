from __future__ import annotations

import re
import tomllib
from pathlib import Path

from pydantic import ValidationError
from semantic_version import Version

from airlock import proc
from airlock.contracts import (
    STRING,
    TARGET_SPEC,
    VERSION_OBJECT,
    ActionSpec,
    ContainerSpec,
    JsonVersion,
    RegexVersion,
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


def parse_manifest(text: str, *, is_historical: bool = False) -> list[TargetSpec]:
    contents = tomllib.loads(text)
    scope = STRING.validate_python(contents.pop("scope", ""))
    if not scope:
        msg = "scope must be nonempty"
        raise ValueError(msg)
    targets = []
    for name, declaration in contents.items():
        try:
            spec = TARGET_SPEC.validate_python(declaration, extra="ignore" if is_historical else "forbid")
        except ValidationError as exc:
            if any(error["type"] == "extra_forbidden" for error in exc.errors()):
                msg = f"Unrecognized key in {name}: {exc}"
                raise ValueError(msg) from exc
            raise
        targets.append(
            spec.model_copy(
                update={
                    "label": spec.label if "label" in spec.model_fields_set else f"{scope}/{name}",
                    "tag_prefix": f"{name}-v",
                }
            )
        )
    return targets


def load_specs(root: Path) -> list[TargetSpec]:
    return parse_manifest((root / "airlock-targets.toml").read_text(encoding="utf-8"))


def parse_version(text: str, source: JsonVersion | RegexVersion) -> str:
    if isinstance(source, JsonVersion):
        field: object = VERSION_OBJECT.validate_json(text)
        for key in source.json_path.split("."):
            field = VERSION_OBJECT.validate_python(field)[key]
        return STRING.validate_python(field)
    try:
        match = re.search(source.regex, text, re.MULTILINE)
    except re.PatternError as exc:
        msg = f"{source.file}: invalid version regex: {exc}"
        raise ValueError(msg) from exc
    if match is None or match.lastindex is None:
        msg = f"could not read version from {source.file}"
        raise ValueError(msg)
    return match[1]


def resolve_repo_path(root: Path, relative: str) -> Path:
    resolved = (root / relative).resolve()
    if Path(relative).is_absolute() or not resolved.is_relative_to(root.resolve()):
        msg = f"release paths must be repository-relative: {relative}"
        raise ValueError(msg)
    return resolved


def build_release_target(root: Path, spec: TargetSpec, version: str) -> ReleaseTarget:
    directory = resolve_repo_path(root, spec.version.file).parent
    build_context = None
    dockerfile = None
    action_directory = None
    if isinstance(spec, ContainerSpec):
        build_context = resolve_repo_path(root, spec.build_context or str(Path(spec.version.file).parent))
        dockerfile = None if spec.dockerfile is None else resolve_repo_path(root, spec.dockerfile)
    if isinstance(spec, ActionSpec):
        action_directory = directory if spec.path is None else resolve_repo_path(root, spec.path)
    return ReleaseTarget(spec, version, directory, build_context, dockerfile, action_directory)


def load_targets(root: Path | None = None) -> list[ReleaseTarget]:
    root = root or proc.find_root()
    return [
        build_release_target(
            root,
            spec,
            parse_version(resolve_repo_path(root, spec.version.file).read_text(encoding="utf-8"), spec.version),
        )
        for spec in load_specs(root)
    ]
