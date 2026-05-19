#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["loguru>=0.7"]
# ///
"""
Idempotent installer for user-scoped CLI tools whose vendors ship a
piped-shell-script bootstrapper (bun, uv, claude, rustup, cargo-binstall).

For each [[install]] block in url_config.toml: skip if `bin` is reachable on
PATH or in a known bootstrap dir (~/.cargo/bin, ~/.bun/bin, ~/.local/bin,
~/.claude/local); else fetch the installer and pipe it to bash with the
block's `args`.

Runs as the invoking user — these installers write into $HOME, so the
script refuses to run as root (otherwise toolchains land in /root rather
than the user's home).

Note: the installers themselves shell out to curl to fetch their binaries.
On a truly fresh system, `apt install curl` (or running configure_with_apt.py, which
installs curl as a prereq) is a precondition.
"""

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.request import urlopen

from loguru import logger

from harness import SRC_DIR, find_binary, start_log_tee

SCRIPT = Path(__file__).resolve()
URL_CONFIG_TOML = SRC_DIR / "url_config.toml"


def install_from_url(name: str, url: str, bin_name: str, args: list[str]) -> None:
    if existing := find_binary(bin_name):
        logger.info(f"Already installed: {bin_name}  ({existing})")
        return

    logger.info(f"Installing {name} from {url}")
    with urlopen(url) as response:
        installer_script = response.read()
    subprocess.run(["bash", "-s", "--", *args], input=installer_script, check=True)

    if found := find_binary(bin_name):
        logger.info(f"Installed: {found}")
    else:
        logger.warning(
            f"{bin_name} not found on PATH or in standard bootstrap dirs "
            "after install — vendor may use a non-standard path"
        )


def main() -> None:
    if os.geteuid() == 0:
        sys.exit(
            "ERROR: run as the invoking user (not root) — these installers "
            "write into $HOME and would land under /root if run as root."
        )

    with URL_CONFIG_TOML.open("rb") as f:
        config = tomllib.load(f)
    installs = config.get("install", [])
    if not installs:
        logger.info(f"No [[install]] blocks in {URL_CONFIG_TOML}; nothing to do")
        return

    log_file = start_log_tee(SCRIPT)
    logger.info(f"Logging this run to {log_file}")
    logger.info(f"Loaded {len(installs)} install(s) from {URL_CONFIG_TOML}")

    for install_block in installs:
        install_from_url(
            install_block["name"],
            install_block["url"],
            install_block.get("bin", install_block["name"]),
            install_block.get("args", []),
        )

    logger.info("Done.")


if __name__ == "__main__":
    main()
