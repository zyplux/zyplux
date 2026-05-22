"""
Idempotent uv-tool installer/updater driven by uv_config.toml.

For each entry in `packages`:
  not installed -> `uv tool install <pkg>`
  installed     -> `uv tool upgrade <pkg>`

Installed tools are detected from a single up-front `uv tool list`, which
announces each tool on a column-0 line as `<name> v<version>` with its
executables indented (`- <bin>`) below.

Packages are processed concurrently via a thread pool; uv serializes
conflicting filesystem work internally with its own locks.

Requires uv to be installed first; run ./src/install_from_urls.py if missing.

Runs as the invoking user — uv writes into ~/.local/share/uv and ~/.local/bin,
so the script refuses to run as root.
"""

import os
import subprocess
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from harness import SRC_DIR, find_binary, start_log_tee, stream_subprocess

SCRIPT = Path(__file__).resolve()
UV_CONFIG_TOML = SRC_DIR / "uv_config.toml"


def list_installed_tools(uv: Path) -> set[str]:
    """Tool names from `uv tool list`. Each tool is announced by a column-0
    line `<name> v<version>`; executable lines below it start with `- ` and
    are ignored."""
    completed = subprocess.run(
        [str(uv), "tool", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        line.split()[0]
        for line in completed.stdout.splitlines()
        if line and not line[0].isspace() and not line.startswith("-")
    }


def install_or_upgrade(uv: Path, name: str, installed: set[str], tag: str) -> None:
    action, verb = (
        ("Upgrading", "upgrade") if name in installed else ("Installing", "install")
    )
    stream_subprocess([str(uv), "tool", verb, name], tag, note=action)


def main() -> None:
    if os.geteuid() == 0:
        sys.exit(
            "ERROR: run as the invoking user (not root) — uv writes into "
            "~/.local and would land under /root if run as root."
        )

    uv = find_binary("uv")
    if not uv:
        sys.exit("ERROR: uv must be installed first. Run ./src/install_from_urls.py.")

    with UV_CONFIG_TOML.open("rb") as f:
        config = tomllib.load(f)
    requested = config.get("packages", [])
    if not requested:
        logger.info(f"No `packages` entries in {UV_CONFIG_TOML}; nothing to do")
        return

    start_log_tee()
    logger.info(f"Running {len(requested)} uv tool(s) in parallel")

    installed = list_installed_tools(uv)

    tag_width = max(len(name) for name in requested)
    failures: list[tuple[str, Exception]] = []
    with ThreadPoolExecutor(max_workers=len(requested)) as pool:
        pending = {
            pool.submit(
                install_or_upgrade,
                uv,
                name,
                installed,
                f"[{name:>{tag_width}}]",
            ): name
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
            f"{len(failures)} of {len(requested)} uv tool(s) failed: "
            + ", ".join(name for name, _ in failures)
        )

    logger.info("Done.")


if __name__ == "__main__":
    main()
