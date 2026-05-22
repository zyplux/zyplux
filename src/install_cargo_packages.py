"""
Idempotent cargo installer/updater driven by cargo_config.toml.

Hands every requested crate to a single `cargo binstall --no-confirm pkg1 pkg2 ...`
call. cargo-binstall resolves each crate's latest release, compares against the
installed version recorded in ~/.cargo/.crates.toml, and installs / upgrades /
skips per crate. Idempotency is built in.

cargo-binstall parallelizes resolution and download across requested crates
inside one process, so a ThreadPool wrapper around N single-crate invocations
would just add process-startup overhead and per-process cache-lock contention
without buying parallelism.

cargo-binstall writes to cargo's own .crates.toml registry, so binstall'd and
source-built packages share one index.

cargo-binstall is invoked by absolute path to sidestep the bootstrap PATH
problem — see logs/sys-conf-py-*.log for context.

Bootstraps cargo-binstall via `cargo install cargo-binstall` if it isn't
already on disk. That's a slow source compile, but only happens once per
fresh system; thereafter cargo-binstall is in cargo_config.toml's package
list and updates itself in the same batch as everything else (version-
aware, ~1s). Requires cargo (from rustup) — run ./src/install_from_urls.py
first if cargo is missing.

Runs as the invoking user — cargo writes into ~/.cargo, so the script refuses
to run as root (toolchains would land under /root otherwise).
"""

import os
import sys
import tomllib
from pathlib import Path

from loguru import logger

from harness import SRC_DIR, find_binary, start_log_tee, stream_subprocess

SCRIPT = Path(__file__).resolve()
CARGO_CONFIG_TOML = SRC_DIR / "cargo_config.toml"


def main() -> None:
    if os.geteuid() == 0:
        sys.exit(
            "ERROR: run as the invoking user (not root) — cargo writes into "
            "~/.cargo and would land under /root if run as root."
        )

    with CARGO_CONFIG_TOML.open("rb") as f:
        config = tomllib.load(f)
    requested = config.get("packages", [])
    if not requested:
        logger.info(f"No `packages` entries in {CARGO_CONFIG_TOML}; nothing to do")
        return

    start_log_tee()

    binstall = find_binary("cargo-binstall")
    if not binstall:
        cargo = find_binary("cargo")
        if not cargo:
            sys.exit(
                "ERROR: cargo not found — run ./src/install_from_urls.py first "
                "(rustup provides cargo)."
            )
        logger.info(
            "cargo-binstall missing — bootstrapping via `cargo install` "
            "(slow source compile; happens once per fresh system)"
        )
        stream_subprocess([str(cargo), "install", "cargo-binstall"])
        binstall = find_binary("cargo-binstall")
        if not binstall:
            sys.exit(
                "ERROR: `cargo install cargo-binstall` succeeded but the binary "
                "is not on PATH or in ~/.cargo/bin. Check cargo's install root."
            )

    logger.info(
        f"Installing/upgrading {len(requested)} crate(s): {', '.join(requested)}"
    )

    stream_subprocess([str(binstall), "--no-confirm", *requested])

    logger.info("Done.")


if __name__ == "__main__":
    main()
