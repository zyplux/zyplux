from __future__ import annotations

import json
import runpy
from typing import TYPE_CHECKING

import pytest
from setup_pm import prepare

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "package.json").write_text(
        json.dumps({
            "packageManager": "pnpm@12.14.0",
            "devEngines": {"runtime": {"name": "node", "version": "26.12.1"}},
        })
    )
    for name in ("pnpm-lock.yaml", "pyproject.toml", "uv.lock"):
        (tmp_path / name).touch()
    return tmp_path


def test_1_1_1_prepares_both_toolchains_from_workspace_pins(workspace: Path) -> None:
    plan = prepare.build_setup_plan(workspace, uv_version="0.13.4")
    assert plan == {
        "pnpm-version": "12.14.0",
        "node-version": "26.12.1",
        "uv-version": "0.13.4",
    }


@pytest.mark.parametrize("name", ["package.json", "pnpm-lock.yaml", "pyproject.toml", "uv.lock"])
def test_1_2_1_requires_both_workspaces_and_lockfiles_before_bootstrapping(workspace: Path, name: str) -> None:
    (workspace / name).unlink()
    with pytest.raises(FileNotFoundError, match=f"{name} is required"):
        prepare.build_setup_plan(workspace, uv_version="0.13.4")


@pytest.mark.parametrize("version", ["latest", "^12.14.0", "12", "12.14.0\ninjected=true", 12, None])
def test_1_2_2_requires_exact_versions_for_executable_cache_keys(version: object) -> None:
    with pytest.raises(ValueError, match="must pin an exact stable version"):
        prepare.validate_version(version, "tool")


@pytest.mark.parametrize("manager", ["npm@12.0.0", 12])
def test_1_2_3_requires_a_pnpm_package_manager(workspace: Path, manager: object) -> None:
    manifest = json.loads((workspace / "package.json").read_text())
    manifest["packageManager"] = manager
    (workspace / "package.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="must declare packageManager"):
        prepare.load_node_versions(workspace)


def test_1_2_4_requires_a_node_runtime(workspace: Path) -> None:
    manifest = json.loads((workspace / "package.json").read_text())
    manifest["devEngines"]["runtime"]["name"] = "bun"
    (workspace / "package.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=r"must declare Node\.js"):
        prepare.load_node_versions(workspace)


def test_1_3_1_accepts_package_manager_integrity_suffixes(workspace: Path) -> None:
    manifest = json.loads((workspace / "package.json").read_text())
    manifest["packageManager"] += "+sha512.integrity"
    (workspace / "package.json").write_text(json.dumps(manifest))
    assert prepare.load_node_versions(workspace) == ("12.14.0", "26.12.1")


def test_1_3_2_writes_github_action_outputs(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    action_output = workspace / "action-output"
    monkeypatch.setenv("GITHUB_WORKSPACE", str(workspace))
    monkeypatch.setenv("GITHUB_OUTPUT", str(action_output))
    monkeypatch.setenv("UV_VERSION", "0.13.4")
    runpy.run_path(prepare.__file__, run_name="__main__")
    assert action_output.read_text().splitlines() == [
        "pnpm-version=12.14.0",
        "node-version=26.12.1",
        "uv-version=0.13.4",
    ]
