"""VersionedCook for [uv] — Python CLI tools in isolated venvs via `uv tool install`/`upgrade`, run concurrently behind uv's own locks. Runs as the invoking user; depends on [url]."""

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from cook_base import PackageListCook, SyncOutcome
from harness import find_binary, stream_subprocess


def parse_tool_list(output: str) -> dict[str, str]:
    """Map tool name -> version from `uv tool list`: each tool is a column-0 `<name> v<version>` line; indented `- <bin>` lines are skipped."""
    versions: dict[str, str] = {}
    for line in output.splitlines():
        if not line or line[0].isspace() or line.startswith("-"):
            continue
        tokens = line.split()
        versions[tokens[0]] = tokens[1].lstrip("v") if len(tokens) > 1 else "unknown"
    return versions


def parse_tool_versions(uv: Path) -> dict[str, str]:
    completed = subprocess.run(
        [str(uv), "tool", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    return parse_tool_list(completed.stdout)


class UvCook(PackageListCook):
    manager = "uv"

    def list_installed(self) -> dict[str, str]:
        uv = find_binary("uv")
        return parse_tool_versions(uv) if uv else {}

    def sync(self, to_install: list[str], to_upgrade: list[str]) -> SyncOutcome:
        work = [("install", n) for n in to_install] + [("upgrade", n) for n in to_upgrade]
        if not work:
            return SyncOutcome("ok")

        uv = find_binary("uv")
        if not uv:
            return SyncOutcome(
                "hard_fail",
                "uv must be installed first; the [url] section must run before [uv].",
            )

        logger.info(f"Running {len(work)} uv tool action(s) in parallel")
        tag_width = max(len(name) for _, name in work)
        failures: list[str] = []
        with ThreadPoolExecutor(max_workers=len(work)) as pool:
            pending = {pool.submit(self._run_one, uv, verb, name, tag_width): name for verb, name in work}
            for future in as_completed(pending):
                name = pending[future]
                try:
                    future.result()
                except Exception as exc:
                    failures.append(name)
                    logger.error(f"{name} failed: {exc}")

        if failures:
            return SyncOutcome(
                "hard_fail",
                f"{len(failures)} uv tool(s) failed: " + ", ".join(failures),
            )
        return SyncOutcome("ok")

    @staticmethod
    def _run_one(uv: Path, verb: str, name: str, tag_width: int) -> None:
        action = "Installing" if verb == "install" else "Upgrading"
        stream_subprocess([str(uv), "tool", verb, name], f"[{name:>{tag_width}}]", note=action)
