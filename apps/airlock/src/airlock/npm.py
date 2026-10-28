from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import typer

from airlock import github, proc
from airlock.content_hash import build_archives, validate_contents
from airlock.contracts import WORKSPACE_PACKAGES, NpmPackage
from airlock.registries import is_published, wait_for_dependencies

if TYPE_CHECKING:
    from airlock.contracts import ReleaseTarget


def validate_workspace(target: ReleaseTarget) -> None:
    workspaces = WORKSPACE_PACKAGES.validate_json(
        proc.run("pnpm", "list", "--recursive", "--depth", "-1", "--json", cwd=proc.find_root())
    )
    workspace = next(
        (workspace for workspace in workspaces if Path(workspace.path).resolve() == target.directory), None
    )
    if workspace is None:
        msg = f"{target.package_name}: {target.directory} is not a pnpm workspace package"
        raise ValueError(msg)
    if workspace.name != target.package_name:
        msg = f"{target.package_name}: workspace package name is {workspace.name}"
        raise ValueError(msg)
    if workspace.private:
        msg = f"{target.package_name}: private workspace packages cannot be published"
        raise ValueError(msg)
    if workspace.version != target.version:
        msg = f"{target.package_name}: workspace version must be {target.version}"
        raise ValueError(msg)


def publish_npm(target: ReleaseTarget) -> None:
    validate_workspace(target)
    if is_published(target):
        wait_for_dependencies([target])
        if github.load_release(target.tag) is None:
            validate_contents(target)
        typer.echo(f"{target.package_name} {target.version} is already published; nothing to do")
        return
    manifest = NpmPackage.model_validate_json((target.directory / "package.json").read_text(encoding="utf-8"))
    if {"prepublishOnly", "publish", "postpublish"}.intersection(manifest.scripts):
        msg = (
            f"{target.package_name}: archive publication requires prepack/prepare/postpack hooks; "
            "publish-only hooks are unsupported"
        )
        raise ValueError(msg)
    with TemporaryDirectory(prefix="airlock-npm-") as directory:
        [archive] = build_archives(target, Path(directory))
        dependencies = validate_contents(target, [archive])
        wait_for_dependencies(dependencies)
        proc.run("pnpm", "publish", str(archive), "--publish-wait-timeout", "0", cwd=target.directory, interactive=True)
        wait_for_dependencies([target])
