from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from airlock import github, proc
from airlock.contracts import DIGEST, ContainerManifest
from airlock.registries import is_container_available

if TYPE_CHECKING:
    from airlock.contracts import ReleaseTarget

CONTAINER_MANIFEST = "release.json"


def is_container_published(target: ReleaseTarget) -> bool:
    release = github.load_release(target.tag, assets=True)
    if not github.has_published_assets(release, target.tag, [Path(CONTAINER_MANIFEST)]):
        return False
    manifest = ContainerManifest.model_validate_json(
        proc.run("gh", "release", "download", target.tag, "--pattern", CONTAINER_MANIFEST, "--output", "-")
    )
    prefix = f"{target.spec.label}@"
    if manifest.version != target.version or not manifest.image.startswith(prefix):
        msg = f"published release {target.tag} has an invalid container manifest"
        raise ValueError(msg)
    digest = DIGEST.validate_python(manifest.image.removeprefix(prefix))
    if not is_container_available(target.spec.label, digest):
        msg = f"published release {target.tag} is missing image {manifest.image}"
        raise ValueError(msg)
    return True


def publish_container(target: ReleaseTarget, notes: str) -> None:
    if is_container_published(target):
        return
    token = os.getenv("GH_TOKEN")
    actor = os.getenv("GITHUB_ACTOR")
    if not token:
        msg = "GH_TOKEN is required to push to GHCR"
        raise ValueError(msg)
    if not actor:
        msg = "GITHUB_ACTOR is required to push to GHCR"
        raise ValueError(msg)
    revision = proc.run("git", "rev-parse", "HEAD")
    versioned = f"{target.spec.label}:{target.version}"
    with TemporaryDirectory(prefix="airlock-container-") as directory:
        digest_file = Path(directory) / "digest"
        manifest = Path(directory) / CONTAINER_MANIFEST
        proc.run("podman", "login", "ghcr.io", "-u", actor, "--password-stdin", stdin=token)
        try:
            dockerfile = [] if target.dockerfile is None else ["--file", str(target.dockerfile)]
            proc.run(
                "podman",
                "build",
                *dockerfile,
                "--label",
                f"org.opencontainers.image.version={target.version}",
                "--label",
                f"org.opencontainers.image.revision={revision}",
                "-t",
                versioned,
                str(target.build_context),
            )
            proc.run("podman", "push", "--digestfile", str(digest_file), versioned)
            digest = DIGEST.validate_python(digest_file.read_text(encoding="utf-8").strip())
            if not is_container_available(target.spec.label, digest):
                msg = f"container push did not publish image {versioned}"
                raise ValueError(msg)
            manifest.write_text(
                json.dumps({"image": f"{target.spec.label}@{digest}", "version": target.version}, separators=(",", ":"))
                + "\n",
                encoding="utf-8",
            )
        finally:
            proc.run("podman", "logout", "ghcr.io")
        github.publish_assets(target.tag, notes, revision, [manifest])
