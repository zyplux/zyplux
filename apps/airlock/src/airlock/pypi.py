from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

from packaging.metadata import Metadata
from packaging.utils import canonicalize_name
from packaging.version import Version

from airlock.targets import load_targets

if TYPE_CHECKING:
    from pathlib import Path

    from airlock.contracts import ReleaseTarget


def load_dependencies(target: ReleaseTarget, archives: list[Path]) -> list[ReleaseTarget]:
    wheels = [archive for archive in archives if archive.suffix == ".whl"]
    if len(wheels) != 1:
        msg = f"{target.spec.label}: Python build must produce exactly one wheel"
        raise ValueError(msg)
    with zipfile.ZipFile(wheels[0]) as wheel:
        files = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        if len(files) != 1:
            msg = f"{target.spec.label}: wheel must contain exactly one METADATA file"
            raise ValueError(msg)
        try:
            metadata = Metadata.from_email(wheel.read(files[0]))
        except ExceptionGroup as exc:
            msg = f"{target.spec.label}: invalid wheel metadata: {exc}"
            raise ValueError(msg) from exc
    if canonicalize_name(metadata.name) != canonicalize_name(target.spec.label) or metadata.version != Version(
        target.version
    ):
        msg = f"{target.spec.label}: wheel identity must match {target.spec.label}@{target.version}"
        raise ValueError(msg)
    requirements = metadata.requires_dist or []
    if not requirements:
        return []
    dependencies = [
        dependency
        for dependency in load_targets()
        if dependency.spec.kind == "pypi"
        and any(
            requirement.url is None
            and canonicalize_name(requirement.name) == canonicalize_name(dependency.spec.label)
            and requirement.specifier.contains(dependency.version, prereleases=True)
            for requirement in requirements
        )
    ]
    if any(dependency.spec.label == target.spec.label for dependency in dependencies):
        msg = f"{target.spec.label}: cyclic production workspace dependency"
        raise ValueError(msg)
    return dependencies
