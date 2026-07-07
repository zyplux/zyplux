"""VersionedCook for [bun] — global npm packages via `bun add -g`, installed versions read from bun's global tree and resolved against the npm registry. Runs as the invoking user; depends on [url] (bun itself)."""

import json
import os
from pathlib import Path

from loguru import logger

from totchef import shell
from totchef.cook_base import PackageListCook, SyncOutcome
from totchef.harness import fetch_latest_concurrent, fetch_url, find_binary

NPM_REGISTRY = "https://registry.npmjs.org/{name}"


def parse_npm_latest(payload: bytes) -> str | None:
    """Latest version from the npm registry's per-package document (the `dist-tags.latest` field)."""
    return json.loads(payload).get("dist-tags", {}).get("latest")


def fetch_npm_latest(name: str) -> str | None:
    return parse_npm_latest(fetch_url(NPM_REGISTRY.format(name=name)))


def bun_install_root() -> Path:
    """Bun's install prefix — `$BUN_INSTALL` when the user set one (binaries land in `$BUN_INSTALL/bin`), else the `~/.bun` default. Resolved at call time so it follows become_user's $HOME drop in a forked child."""
    return Path(os.environ["BUN_INSTALL"]) if os.environ.get("BUN_INSTALL") else Path.home() / ".bun"


def global_modules_dir() -> Path:
    """Where `bun add -g` unpacks packages, under the install root."""
    return bun_install_root() / "install/global/node_modules"


def read_package_version(package_json: Path) -> str | None:
    try:
        return json.loads(package_json.read_text()).get("version")
    except OSError, json.JSONDecodeError:
        return None


def ensure_node_shim(bun: Path) -> None:
    """Drop a `node` symlink to bun in bun's install bin dir (on PATH, user-owned), so node-shebang global CLIs (e.g. `pi`) resolve a runtime — bun runs in node-compat mode when invoked as `node`, and `bun add -g` leaves a package's `#!/usr/bin/env node` shebang untouched. The link lives beside the global bins it serves while pointing at the real bun binary wherever it sits. Best-effort: idempotent, refuses to clobber a real `node`, and a failure to link only warns."""
    node = bun_install_root() / "bin" / "node"
    try:
        if node.is_symlink():
            if node.resolve() == bun.resolve():
                return
            node.unlink()
        elif node.exists():
            logger.warning(f"leaving {node} as-is — not a symlink, won't clobber a real node runtime")
            return
        node.parent.mkdir(parents=True, exist_ok=True)
        node.symlink_to(bun)
    except OSError as exc:
        logger.warning(f"could not link {node} -> bun: {exc}")
        return
    logger.info(f"linked {node} -> {bun} so bun serves as the node runtime")


def parse_installed_globals(modules_dir: Path) -> dict[str, str]:
    """Map package name -> installed version by reading each `package.json` under bun's global node_modules, descending one level into `@scope` directories."""
    if not modules_dir.is_dir():
        return {}
    versions: dict[str, str] = {}
    for entry in modules_dir.iterdir():
        if entry.name.startswith("@"):
            for scoped in entry.iterdir():
                if version := read_package_version(scoped / "package.json"):
                    versions[f"{entry.name}/{scoped.name}"] = version
        elif version := read_package_version(entry / "package.json"):
            versions[entry.name] = version
    return versions


class BunCook(PackageListCook):
    def list_installed(self) -> dict[str, str]:
        return parse_installed_globals(global_modules_dir())

    def find_latest(self, names: list[str]) -> dict[str, str | None]:
        return fetch_latest_concurrent(names, fetch_npm_latest)

    def sync(self, to_install: list[str], to_upgrade: list[str]) -> SyncOutcome:
        targets = to_install + to_upgrade
        bun = find_binary("bun")
        if not bun:
            if targets:
                return SyncOutcome(
                    "hard_fail",
                    "bun not found — the [url] section (bun) must run before [bun].",
                )
            return SyncOutcome("ok")

        os.environ["BUN_INSTALL"] = str(bun_install_root())
        ensure_node_shim(bun)
        if not targets:
            return SyncOutcome("ok")

        logger.info(f"Installing/upgrading {len(targets)} bun global(s): " + ", ".join(targets))
        shell.stream([str(bun), "add", "-g", "--ignore-scripts", *targets])
        return SyncOutcome("ok")
