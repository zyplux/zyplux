"""Fixtures for the prose-style tests. A test names the fixtures it needs and reads top-to-bottom like a user story; the only things mocked are the system boundaries — bash (`totchef.shell`), network (`harness.urlopen`), the home directory, and the host (discoverable binaries + OS release).

- `terminal` (autouse) — the bash double; patched over `totchef.shell.run`/`stream` for every test, so no test can shell out for real.
- `http` (autouse) — the network double; patched over `harness.urlopen`, so no test can reach the real network (an un-programmed URL raises).
- `home` (autouse) — `$HOME` redirected to a temp dir, so per-user cooks (`settings`, `chromium_flags`, `desktop`) write under it instead of the real home. Returns the Path.
- `system` (autouse) — the host double: PATH isolated to an empty bin dir (so no real tool leaks in) and `platform.freedesktop_os_release` pinned. `has(...)` provisions a binary, `running_release(...)` sets the codename.
- `recipe` — the operator's recipe.toml, built with `declares(...)`. Point file/repo paths at pytest's `tmp_path`.
- `totchef` — the user action (`plan`/`up`/`lint`), run against `recipe`.

A `fresh_registry` autouse fixture clears the cached cook registry around every test, so a local-cook drop-in (or HOME redirection) never leaks between tests.
"""

import platform
from collections.abc import Generator
from pathlib import Path

import pytest

from totchef import harness, shell
from totchef.registry import cook_registry
from framework import FakeHttp, FakeSystem, FakeTerminal, RecipeBuilder, Totchef


@pytest.fixture(autouse=True)
def terminal(monkeypatch: pytest.MonkeyPatch) -> FakeTerminal:
    """The single mocked bash surface: every cook calls `shell.run`/`shell.stream` module-qualified, so patching these two names intercepts all bash execution."""
    fake = FakeTerminal()
    monkeypatch.setattr(shell, "run", fake.run)
    monkeypatch.setattr(shell, "stream", fake.stream)
    return fake


@pytest.fixture(autouse=True)
def http(monkeypatch: pytest.MonkeyPatch) -> FakeHttp:
    """The single mocked network surface: every `fetch_url` resolves `urlopen` in harness's globals at call time, so patching `harness.urlopen` intercepts all fetches."""
    fake = FakeHttp()
    monkeypatch.setattr(harness, "urlopen", fake.urlopen)
    return fake


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect `$HOME` to a temp dir so `Path.home()` (and `~`) land there, isolating per-user cooks from the real home."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    return home_dir


@pytest.fixture(autouse=True)
def system(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeSystem:
    """Isolate the host: PATH points at an empty bin dir (so `find_binary`/`shutil.which` see only what a test provisions) and the OS release is pinned (so apt_repo's `{release}` substitution is deterministic, not the host's codename)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir))
    fake = FakeSystem(bin_dir)
    monkeypatch.setattr(platform, "freedesktop_os_release", lambda: {"VERSION_CODENAME": fake.release})
    return fake


@pytest.fixture(autouse=True)
def fresh_registry() -> Generator[None]:
    """The cook registry is cached and HOME-dependent (it scans `~/.config/totchef/cooks`); clear it around every test so a local-cook drop-in never leaks."""
    cook_registry.cache_clear()
    yield
    cook_registry.cache_clear()


@pytest.fixture
def recipe() -> RecipeBuilder:
    return RecipeBuilder()


@pytest.fixture
def totchef(recipe: RecipeBuilder, terminal: FakeTerminal) -> Totchef:
    return Totchef(recipe, terminal)
