(
    """Container fixtures for §7.3.2/§8.3.1: real OS state behind a real sudo, via `totchef up` """
    """in a throwaway container; skipped without podman."""
)

import base64
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTAINER_DIR = Path(__file__).parent / "container"
CONTAINERFILE = CONTAINER_DIR / "Containerfile"
IGNOREFILE = CONTAINER_DIR / ".containerignore"
IMAGE = "totchef-test:latest"
RESULT_MARKER = "@@@RESULT@@@"

podman = shutil.which("podman")

# Captured before any test runs. The story suite's autouse fixtures redirect $HOME and
# isolate $PATH in-process; rootless podman keys its image store off $HOME and needs its
# runtime helpers on $PATH, so podman must run with the real environment, not the test's.
CLEAN_ENV = dict(os.environ)


@dataclass
class ContainerRun:
    (
        """What a `totchef up` inside the container produced: each probed artifact's owner """
        """(`stat -c %U`), the log file's owner, and the full transcript."""
    )

    transcript: str
    owners: dict[str, str | None] = field(default_factory=dict)
    log_owner: str | None = None


@pytest.fixture(scope="session")
def container_image() -> str:
    if podman is None:
        pytest.skip("podman not installed")
    build = subprocess.run(
        [podman, "build", "-t", IMAGE, "-f", str(CONTAINERFILE), "--ignorefile", str(IGNOREFILE), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        env=CLEAN_ENV,
        check=False,
    )
    if build.returncode != 0:
        pytest.fail(f"podman build failed:\n{build.stdout}\n{build.stderr}")
    return IMAGE


@pytest.fixture(scope="session")
def apply_in_container(container_image: str) -> Callable[[str, list[str], dict[str, str] | None], ContainerRun]:
    (
        """Run `totchef up` against `recipe` in a fresh container as the non-root `tester`, """
        """reporting the owner of each `artifacts` path and log file. `extra_files` (path -> """
        """content) is written before `up` runs, e.g. a config-dir cook drop-in."""
    )
    assert podman is not None
    binary = podman

    def apply(recipe: str, artifacts: list[str], extra_files: dict[str, str] | None = None) -> ContainerRun:
        recipe_b64 = base64.b64encode(recipe.encode()).decode()
        probes = "\n".join(
            f'stat -c "OWNER %U {path}" "{path}" 2>/dev/null || echo "MISSING {path}"' for path in artifacts
        )
        setup = "\n".join(
            f"mkdir -p {shlex.quote(str(Path(path).parent))} && "
            f"echo {base64.b64encode(content.encode()).decode()} | base64 -d > {shlex.quote(path)}"
            for path, content in (extra_files or {}).items()
        )
        script = (
            "set -e\n"
            f"{setup}\n"
            f"echo {recipe_b64} | base64 -d > ~/recipe.toml\n"
            "totchef up --recipe ~/recipe.toml || true\n"
            f"echo {RESULT_MARKER}\n"
            f"{probes}\n"
            'for log in ~/.local/state/totchef/logs/*.log; do stat -c "LOG %U" "$log"; done 2>/dev/null || true\n'
        )
        proc = subprocess.run(
            [binary, "run", "--rm", container_image, "bash", "-lc", script],
            capture_output=True,
            text=True,
            env=CLEAN_ENV,
            check=False,
        )
        return _parse(proc.stdout + proc.stderr)

    return apply


def _parse(transcript: str) -> ContainerRun:
    run = ContainerRun(transcript=transcript)
    _, _, tail = transcript.partition(RESULT_MARKER)
    for line in tail.splitlines():
        if line.startswith("OWNER "):
            _, owner, path = line.split(" ", 2)
            run.owners[path] = owner
        elif line.startswith("MISSING "):
            run.owners[line.removeprefix("MISSING ")] = None
        elif line.startswith("LOG "):
            run.log_owner = line.removeprefix("LOG ").strip()
    return run
