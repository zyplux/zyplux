from __future__ import annotations

import logging
import subprocess

TAG_REF = "refs/tags/v1"
logger = logging.getLogger(__name__)


def run_git(*args: str) -> str:
    return subprocess.run(("git", *args), check=True, text=True, stdout=subprocess.PIPE).stdout.strip()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    remote_tag = run_git("ls-remote", "--refs", "origin", TAG_REF)
    tag_commit = remote_tag.split()[0] if remote_tag else ""
    run_git("fetch", "--no-tags", "origin", "main")
    commit = run_git("rev-parse", "HEAD")
    if commit != run_git("rev-parse", "FETCH_HEAD"):
        logger.info("Skipping v1 publication: checkout is no longer current main")
        return
    run_git("push", f"--force-with-lease={TAG_REF}:{tag_commit}", "origin", f"{commit}:{TAG_REF}")


if __name__ == "__main__":
    main()
