from __future__ import annotations

import re
import tomllib
from pathlib import Path

from pydantic import ValidationError

from airlock import proc
from airlock.contracts import (
    STRING,
    TARGET_SPEC,
    VERSION_OBJECT,
    ContainerSpec,
    JsonVersion,
    RegexVersion,
    ReleaseTarget,
    TargetSpec,
)


def parse_manifest(text: str) -> list[TargetSpec]:
    contents = tomllib.loads(text)
    scope = STRING.validate_python(contents.pop("scope", ""))
    if not scope:
        msg = "scope must be nonempty"
        raise ValueError(msg)
    targets = []
    for name, declaration in contents.items():
        try:
            spec = TARGET_SPEC.validate_python(declaration)
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
    match = re.search(source.regex, text, re.MULTILINE)
    if match is None or match.lastindex is None:
        msg = f"could not read version from {source.file}"
        raise ValueError(msg)
    return match[1]


def resolve_build_path(root: Path, relative: str) -> Path:
    resolved = (root / relative).resolve()
    if Path(relative).is_absolute() or not resolved.is_relative_to(root.resolve()):
        msg = f"container build paths must be repository-relative: {relative}"
        raise ValueError(msg)
    return resolved


def load_targets(root: Path | None = None) -> list[ReleaseTarget]:
    root = root or proc.find_root()
    targets = []
    for spec in load_specs(root):
        version = parse_version((root / spec.version.file).read_text(encoding="utf-8"), spec.version)
        build_context = None
        dockerfile = None
        if isinstance(spec, ContainerSpec):
            build_context = resolve_build_path(root, spec.build_context or str(Path(spec.version.file).parent))
            dockerfile = None if spec.dockerfile is None else resolve_build_path(root, spec.dockerfile)
        targets.append(ReleaseTarget(spec, version, root / Path(spec.version.file).parent, build_context, dockerfile))
    return targets


def resolve_tag(tag: str) -> ReleaseTarget:
    target = next((target for target in load_targets() if tag.startswith(target.spec.tag_prefix)), None)
    if target is None:
        msg = f"no release target in airlock-targets.toml owns tag '{tag}'"
        raise ValueError(msg)
    if tag != target.tag:
        msg = f"tag '{tag}' does not match {target.spec.label} version '{target.version}' (expected '{target.tag}')"
        raise ValueError(msg)
    return target
