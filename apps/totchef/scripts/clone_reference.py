#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""Shallow-clone a reference repo into reference_clones/ for browsing.

Usage: clone_reference.py <owner/name|url> [ref]
With a ref, keep history back to (but excluding) that commit/tag; otherwise
clone a single commit. Not part of `up`/idempotency — a manual dev helper.
"""

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    if not 2 <= len(sys.argv) <= 3:
        sys.exit("usage: clone_reference.py <owner/name|url> [ref]")
    repo = sys.argv[1]
    ref = sys.argv[2] if len(sys.argv) == 3 else ""

    is_url = "://" in repo or repo.startswith("git@")
    url = repo if is_url else f"https://github.com/{repo}.git"
    dest = Path("reference_clones") / Path(repo).name.removesuffix(".git")

    if dest.exists():
        input(f"{dest} exists — rm -rf and re-clone? [enter to continue, ^C to abort] ")
        shutil.rmtree(dest)

    depth_args = ["--shallow-exclude", ref] if ref else ["--depth", "1"]
    subprocess.run(["git", "clone", *depth_args, "--single-branch", url, str(dest)], check=True)


if __name__ == "__main__":
    main()
