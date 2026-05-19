#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["loguru>=0.7"]
# ///
"""
Idempotent cargo package installer driven by cargo_config.toml.

For each `packages` entry: skip if `cargo install --list` already reports
the crate; else invoke cargo-binstall by absolute path (sidestepping the
bootstrap PATH problem — see logs/install_from_urls-*.log for context).

Requires cargo and cargo-binstall to be installed first; run
./src/install_from_urls.py if either is missing.

Runs as the invoking user — cargo writes into ~/.cargo, so the script
refuses to run as root (toolchains would land under /root otherwise).
"""

import os
import subprocess
import sys
import tomllib
from pathlib import Path

from loguru import logger

from harness import SRC_DIR, find_binary, start_log_tee

SCRIPT = Path(__file__).resolve()
CARGO_CONFIG_TOML = SRC_DIR / "cargo_config.toml"


def list_installed_crates(cargo: Path) -> set[str]:
    """Crate names from `cargo install --list`. Each crate is announced by a
    column-0 line ending in `:` (e.g. `just v1.36.0:`); binary names below it
    are indented and ignored."""
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


def install_crate(binstall: Path, name: str) -> None:
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
    requested_crates = config.get("packages", [])
    if not requested_crates:
        logger.info(f"No `packages` entries in {CARGO_CONFIG_TOML}; nothing to do")
        return

    log_file = start_log_tee(SCRIPT)
    logger.info(f"Logging this run to {log_file}")
    logger.info(f"Using cargo:          {cargo}")
    logger.info(f"Using cargo-binstall: {binstall}")
    logger.info(f"Loaded {len(requested_crates)} package(s) from {CARGO_CONFIG_TOML}")

    installed_crates = list_installed_crates(cargo)
    for name in requested_crates:
        if name in installed_crates:
            logger.info(f"Already installed: {name}")
            continue
        install_crate(binstall, name)

    logger.info("Done.")


if __name__ == "__main__":
    main()
