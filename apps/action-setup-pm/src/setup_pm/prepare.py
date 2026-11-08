from __future__ import annotations

import json
import os
import re
from pathlib import Path

VERSION = re.compile(r"\d+\.\d+\.\d+")


def validate_version(version: object, label: str) -> str:
    if not isinstance(version, str) or VERSION.fullmatch(version) is None:
        message = f"{label} must pin an exact stable version"
        raise ValueError(message)
    return version


def load_node_versions(workspace: Path) -> tuple[str, str]:
    manifest = json.loads((workspace / "package.json").read_text(encoding="utf-8"))
    manager = manifest["packageManager"]
    if not isinstance(manager, str) or not manager.startswith("pnpm@"):
        message = "package.json must declare packageManager: pnpm@<version>"
        raise ValueError(message)
    pnpm_version = validate_version(manager.removeprefix("pnpm@"), "packageManager")
    if tuple(map(int, pnpm_version.split("."))) < (11, 1, 0):
        message = "packageManager must pin pnpm 11.1.0 or newer for --no-runtime"
        raise ValueError(message)
    runtime = manifest["devEngines"]["runtime"]
    if runtime["name"] != "node":
        message = "devEngines.runtime must declare Node.js"
        raise ValueError(message)
    return pnpm_version, validate_version(runtime["version"], "devEngines.runtime.version")


def build_setup_plan(workspace: Path, *, uv_version: str, package_managers: str = "pnpm uv") -> dict[str, str]:
    managers = set(package_managers.split())
    if not managers or managers - {"pnpm", "uv"}:
        message = "package-managers must select pnpm, uv, or both"
        raise ValueError(message)
    manifests = []
    if "pnpm" in managers:
        manifests.extend(("package.json", "pnpm-lock.yaml"))
    if "uv" in managers:
        manifests.extend(("pyproject.toml", "uv.lock"))
    for name in manifests:
        if not (workspace / name).is_file():
            message = f"{name} is required"
            raise FileNotFoundError(message)
    plan = {}
    if "pnpm" in managers:
        pnpm_version, node_version = load_node_versions(workspace)
        plan.update({"pnpm-version": pnpm_version, "node-version": node_version})
    if "uv" in managers:
        plan["uv-version"] = validate_version(uv_version, "uv-version")
    return plan


def main() -> None:
    plan = build_setup_plan(
        Path(os.environ["GITHUB_WORKSPACE"]),
        uv_version=os.environ["UV_VERSION"],
        package_managers=os.environ["PACKAGE_MANAGERS"],
    )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        stream.writelines(f"{name}={version}\n" for name, version in plan.items())


if __name__ == "__main__":
    main()
