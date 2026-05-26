"""VersionedCook for [cargo] — crates via a single batched `cargo binstall` that does its own per-crate skip-if-current, bootstrapping cargo-binstall once. Runs as the invoking user; depends on [url]."""

import subprocess
from pathlib import Path

from loguru import logger

from cook_base import PackageListCook, SyncOutcome
from harness import find_binary, stream_subprocess


def parse_crate_list(output: str) -> dict[str, str]:
    """Map crate name -> version from `cargo install --list`: each crate is a column-0 `<name> v<version>:` line, binaries are indented."""
    versions: dict[str, str] = {}
    for line in output.splitlines():
        if not line or line[0].isspace():
            continue
        tokens = line.rstrip(":").split()
        if len(tokens) >= 2 and tokens[1].startswith("v"):
            versions[tokens[0]] = tokens[1].lstrip("v")
    return versions


def parse_installed_crates() -> dict[str, str]:
    cargo = find_binary("cargo")
    if not cargo:
        return {}
    completed = subprocess.run([str(cargo), "install", "--list"], capture_output=True, text=True)
    return parse_crate_list(completed.stdout)


class CargoCook(PackageListCook):
    manager = "cargo-binstall"

    def list_installed(self) -> dict[str, str]:
        return parse_installed_crates()

    def _ensure_binstall(self) -> Path | None:
        if binstall := find_binary("cargo-binstall"):
            return binstall
        cargo = find_binary("cargo")
        if not cargo:
            return None
        logger.info("cargo-binstall missing — bootstrapping via `cargo install` (slow source compile; happens once per fresh system)")
        stream_subprocess([str(cargo), "install", "cargo-binstall"])
        return find_binary("cargo-binstall")

    def sync(self, to_install: list[str], to_upgrade: list[str]) -> SyncOutcome:
        targets = to_install + to_upgrade
        if not targets:
            return SyncOutcome("ok")

        if not find_binary("cargo"):
            return SyncOutcome(
                "hard_fail",
                "cargo not found — the [url] section (rustup) must run before [cargo].",
            )
        binstall = self._ensure_binstall()
        if not binstall:
            return SyncOutcome(
                "hard_fail",
                "cargo-binstall is not on PATH or in ~/.cargo/bin after bootstrap. Check cargo's install root.",
            )

        logger.info(f"Installing/upgrading {len(targets)} crate(s): " + ", ".join(targets))
        stream_subprocess([str(binstall), "--no-confirm", *targets])
        return SyncOutcome("ok")
