from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

from cli_fixture import REPO_ROOT


def test_14_1_1_passes_publint_for_every_built_npm_archive(tmp_path: Path) -> None:
    declarations = tomllib.loads((REPO_ROOT / "airlock-targets.toml").read_text(encoding="utf-8"))
    declarations.pop("scope")
    for target in declarations.values():
        if target["kind"] == "npm":
            directory = REPO_ROOT / Path(target["version"]["file"]).parent
            subprocess.run(
                ["pnpm", "pack", "--out", str(tmp_path / f"{directory.name}.tgz")], cwd=directory, check=True
            )


def test_14_1_2_installs_airlock_from_its_python_wheel(tmp_path: Path) -> None:
    subprocess.run(
        ["uv", "build", "--package", "zyplux-airlock", "--out-dir", str(tmp_path)], cwd=REPO_ROOT, check=True
    )
    wheel = next(tmp_path.glob("*.whl"))
    command = ["uv", "run", "--isolated", "--no-project", "--with", str(wheel), "airlock"]
    execution = subprocess.run([*command, "--version"], cwd=tmp_path, text=True, capture_output=True, check=True)
    project = tomllib.loads((REPO_ROOT / "apps/airlock/pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert execution.stdout.strip() == project["version"]
    help_page = subprocess.run([*command, "--help"], cwd=tmp_path, text=True, capture_output=True, check=True)
    assert all(command in help_page.stdout for command in ("prepare", "plan", "publish"))
