#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["loguru>=0.7"]
# ///
"""
Idempotent cargo installer/updater driven by cargo_config.toml.

For each `packages` entry:
  not installed -> `cargo binstall --no-confirm <pkg>`
  installed     -> `cargo binstall --force --no-confirm <pkg>` (re-fetch latest)

Installed crates are detected from a single up-front `cargo install --list`
snapshot. Each crate is announced by a column-0 line ending in `:`
(e.g. `just v1.36.0:`); binary names below it are indented and ignored.
cargo-binstall writes to cargo's own .crates.toml registry, so binstall'd
and source-built packages share one index.

Packages are processed concurrently via a thread pool; cargo and binstall
serialize conflicting filesystem work via the cargo package-cache lock.

cargo-binstall is invoked by absolute path to sidestep the bootstrap PATH
problem — see logs/install_from_urls-*.log for context.

Requires cargo and cargo-binstall to be installed first; run
./src/install_from_urls.py if either is missing.

Runs as the invoking user — cargo writes into ~/.cargo, so the script
refuses to run as root (toolchains would land under /root otherwise).
"""

import os
import subprocess
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from harness import SRC_DIR, find_binary, start_log_tee

SCRIPT = Path(__file__).resolve()
CARGO_CONFIG_TOML = SRC_DIR / "cargo_config.toml"


def list_installed_crates(cargo: Path) -> set[str]:
    completed = subprocess.run(
        [str(cargo), "install", "--list"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        line.split()[0]
        for line in completed.stdout.splitlines()
        if line and not line[0].isspace() and line.rstrip().endswith(":")
    }


def install_or_upgrade(binstall: Path, name: str, installed: set[str]) -> None:
    if name in installed:
        logger.info(f"Upgrading {name} via cargo-binstall --force")
        subprocess.run([str(binstall), "--force", "--no-confirm", name], check=True)
    else:
        logger.info(f"Installing {name} via cargo-binstall")
        subprocess.run([str(binstall), "--no-confirm", name], check=True)


def main() -> None:
    if os.geteuid() == 0:
        sys.exit(
            "ERROR: run as the invoking user (not root) — cargo writes into "
            "~/.cargo and would land under /root if run as root."
        )

    cargo = find_binary("cargo")
    binstall = find_binary("cargo-binstall")
    if not cargo or not binstall:
        sys.exit(
            "ERROR: cargo and cargo-binstall must be installed first. "
            "Run ./src/install_from_urls.py."
        )

    with CARGO_CONFIG_TOML.open("rb") as f:
        config = tomllib.load(f)
    requested = config.get("packages", [])
    if not requested:
        logger.info(f"No `packages` entries in {CARGO_CONFIG_TOML}; nothing to do")
        return

    log_file = start_log_tee(SCRIPT)
    logger.info(f"Logging this run to {log_file}")
    logger.info(f"Using cargo:          {cargo}")
    logger.info(f"Using cargo-binstall: {binstall}")
    logger.info(f"Running {len(requested)} crate(s) in parallel from {CARGO_CONFIG_TOML}")

    installed = list_installed_crates(cargo)

    failures: list[tuple[str, Exception]] = []
    with ThreadPoolExecutor(max_workers=len(requested)) as pool:
        pending = {
            pool.submit(install_or_upgrade, binstall, name, installed): name
            for name in requested
        }
        for future in as_completed(pending):
            name = pending[future]
            try:
                future.result()
            except Exception as exc:
                failures.append((name, exc))
                logger.error(f"{name} failed: {exc}")

    if failures:
        sys.exit(
            f"{len(failures)} of {len(requested)} crate(s) failed: "
            + ", ".join(name for name, _ in failures)
        )

    logger.info("Done.")


if __name__ == "__main__":
    main()
