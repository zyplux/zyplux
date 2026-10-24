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
