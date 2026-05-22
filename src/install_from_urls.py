#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["loguru>=0.7"]
# ///
"""
Idempotent installer/updater for user-scoped CLI tools whose vendors ship
a piped-shell-script bootstrapper (bun, uv, claude, rustup, cargo-binstall,
herdr).

For each [[install]] block in url_config.toml the action depends on whether
`bin` is already reachable (PATH or a known bootstrap dir like ~/.cargo/bin,
~/.bun/bin, ~/.local/bin, ~/.claude/local):

  not installed -> fetch `url` and pipe it to bash with the block's `args`
  installed     -> dispatch on `update_action`:
                     list of strings        -> run `<bin> <update_action...>`
                     "rerun-installer"      -> re-pipe the install URL into bash
                     absent                 -> no update; log and move on

Not every vendor's installer is safe to re-run as an updater, so the
config picks the strategy per tool rather than assuming one.

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from harness import SRC_DIR, fetch_url, find_binary, start_log_tee

SCRIPT = Path(__file__).resolve()
URL_CONFIG_TOML = SRC_DIR / "url_config.toml"

RERUN_INSTALLER = "rerun-installer"


def run_installer(url: str, args: list[str]) -> None:
    subprocess.run(["bash", "-s", "--", *args], input=fetch_url(url), check=True)


def update_existing(
    name: str,
    url: str,
    bin_path: Path,
    args: list[str],
    update_action: list[str] | str | None,
) -> None:
    if isinstance(update_action, list) and update_action:
        logger.info(f"Updating {name} via `{bin_path.name} {' '.join(update_action)}`")
        subprocess.run([str(bin_path), *update_action], check=True)
    elif update_action == RERUN_INSTALLER:
        logger.info(f"Updating {name} by re-running installer from {url}")
        run_installer(url, args)
    elif update_action is None:
        logger.info(f"No update_action configured for {name}; leaving {bin_path} as-is")
    else:
        raise ValueError(
            f"unrecognized update_action for {name}: {update_action!r} "
            f"(expected a list of args, the string {RERUN_INSTALLER!r}, or absent)"
        )


def install_from_url(
    name: str,
    url: str,
    bin_name: str,
    args: list[str],
    update_action: list[str] | str | None,
) -> None:
    if existing := find_binary(bin_name):
        update_existing(name, url, existing, args, update_action)
        return

    logger.info(f"Installing {name} from {url}")
    run_installer(url, args)

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
    logger.info(f"Running {len(installs)} install(s) in parallel from {URL_CONFIG_TOML}")

    failures: list[tuple[str, Exception]] = []
    with ThreadPoolExecutor(max_workers=len(installs)) as pool:
        pending = {
            pool.submit(
                install_from_url,
                block["name"],
                block["url"],
                block.get("bin", block["name"]),
                block.get("args", []),
                block.get("update_action"),
            ): block["name"]
            for block in installs
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
            f"{len(failures)} of {len(installs)} installer(s) failed: "
            + ", ".join(name for name, _ in failures)
        )

    logger.info("Done.")


if __name__ == "__main__":
    main()
