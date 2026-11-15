"""Read npm workspace package names, dependencies and test scripts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cerberus.workspaces.workspace_members import ts_member_dirs

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo


@dataclass(frozen=True)
class PackageInfo:
    directory: str
    manifest: dict[str, Any]


def list_packages(repo: Repo, ctx: Context) -> dict[str, PackageInfo]:
    packages = {}
    for directory in ts_member_dirs(repo, ctx, ctx.paths(repo)):
        path = f"{directory}/package.json" if directory else "package.json"
        content = ctx.file(repo, path)
        if content is None:
            continue
        manifest = json.loads(content)
        if isinstance(manifest, dict) and isinstance(manifest.get("name"), str):
            packages[manifest["name"]] = PackageInfo(directory, manifest)
    return packages


def list_dependencies(manifest: dict[str, Any]) -> set[str]:
    return {
        name
        for category in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
        for name in manifest.get(category, {})
    }


def is_library(package: PackageInfo) -> bool:
    return package.directory.split("/", 1)[0] == "packages"


def parse_test_script(content: str) -> str:
    try:
        manifest = json.loads(content)
    except json.JSONDecodeError:
        return ""
    scripts = manifest.get("scripts") if isinstance(manifest, dict) else None
    script = scripts.get("test") if isinstance(scripts, dict) else None
    return script if isinstance(script, str) else ""
