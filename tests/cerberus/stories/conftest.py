"""Trusted seam boundary for cerberus's own story tests.

`cerberus.checks.py_test_seam` forbids a story test file from importing
`cerberus` internals beyond the root package's public surface (`__version__`)
and, for cli apps, `cerberus.cli`'s public surface — see that module's
docstring for the exact rule. `conftest.py` files are deliberately never
scanned by the check (mirroring how the TS seam check trusts an alias
target's own imports), so this module is the one sanctioned place a story
test's internal-access needs get satisfied.

Every fixture below hands back either a ready-made value (a `Repo`, a built
`Context`, a `CheckResult` from actually running a check) or an internal
class/enum itself (`Status`, `Finding`, `Scope`) as a fixture return value —
never as something a story test would need an `import` statement to reach.
Checks are always selected by their id STRING (`checks.BY_ID[check_id]`), so
a story test never names — and therefore never imports — the check submodule
it exercises.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from cerberus import checks, config, context, proc, registries
from cerberus.checks.rumdl_config_check import CANONICAL as _RUMDL_CANONICAL
from cerberus.model import Finding, Repo, Scope, Status
from cerberus.source import GitHistoryUnavailableError, LocalSource

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.context import Context
    from cerberus.model import CheckResult

type RunCheck = Callable[[str, Repo, Context], CheckResult]
type RunCheckWithFiles = Callable[[str, dict[str, str]], CheckResult]
type RunCheckOnDisk = Callable[..., CheckResult]
type MakeContext = Callable[..., Context]
type RegisterFakeCheck = Callable[[str, Callable[[Repo, Context], CheckResult]], None]


@pytest.fixture
def repo() -> Repo:
    return Repo("demo")


@pytest.fixture
def ctx() -> Context:
    return context.local_context(config.load(), Path())


@pytest.fixture
def make_context() -> MakeContext:
    def _make(root: Path, *, fix: bool = False) -> Context:
        return context.local_context(config.load(), root, fix=fix)

    return _make


@pytest.fixture
def run_check() -> RunCheck:
    def _run(check_id: str, repo: Repo, ctx: Context) -> CheckResult:
        return checks.BY_ID[check_id].run(repo, ctx)

    return _run


@pytest.fixture
def run_check_with_files(
    repo: Repo, ctx: Context, run_check: RunCheck, monkeypatch: pytest.MonkeyPatch
) -> RunCheckWithFiles:
    """Run a check by id against virtual file content, keyed by repo-relative path.

    A path absent from `files` reads as "file does not exist" (`None`), same as
    a real repo missing that path.
    """

    def _run(check_id: str, files: dict[str, str]) -> CheckResult:
        monkeypatch.setattr(ctx, "file", lambda _repo, path: files.get(path))
        return run_check(check_id, repo, ctx)

    return _run


@pytest.fixture
def run_check_on_disk(tmp_path: Path, make_context: MakeContext, run_check: RunCheck) -> RunCheckOnDisk:
    """Run a check by id against real files on disk — the `--fix` / real-repo variant.

    Writes `files` (repo-relative path -> content) under a fresh `tmp_path`
    before running, so a fixing check can rewrite them and the test can then
    read the result back off disk.
    """

    def _run(check_id: str, files: dict[str, str], *, fix: bool = False) -> CheckResult:
        for path, content in files.items():
            target = tmp_path / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        disk_ctx = make_context(tmp_path, fix=fix)
        return run_check(check_id, disk_ctx.repos()[0], disk_ctx)

    return _run


@pytest.fixture
def register_fake_check(monkeypatch: pytest.MonkeyPatch) -> RegisterFakeCheck:
    """Swap a registered check's `run` callable for a fake, keeping its id/summary/scope."""

    def _register(check_id: str, run: Callable[[Repo, Context], CheckResult]) -> None:
        original = checks.BY_ID[check_id]
        fake = checks.Check(original.id, original.summary, original.scope, run)
        monkeypatch.setitem(checks.BY_ID, check_id, fake)

    return _register


@pytest.fixture
def status() -> type[Status]:
    return Status


@pytest.fixture
def finding() -> type[Finding]:
    return Finding


@pytest.fixture
def scope() -> type[Scope]:
    return Scope


@pytest.fixture
def git_history_unavailable_error() -> type[GitHistoryUnavailableError]:
    return GitHistoryUnavailableError


@pytest.fixture
def local_source() -> type[LocalSource]:
    return LocalSource


@pytest.fixture
def no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch away the `git` binary so a story test can exercise the git-unavailable path."""
    monkeypatch.setattr(proc.shutil, "which", lambda _tool: None)


@pytest.fixture
def rumdl_canonical() -> str:
    return _RUMDL_CANONICAL


@pytest.fixture
def known_check_ids() -> tuple[str, ...]:
    return tuple(checks.BY_ID)


@dataclass
class FakeRegistry:
    """An in-memory double for `cerberus.registries`' single HTTPS boundary."""

    payloads: dict[tuple[str, str], object] = field(default_factory=dict)
    requests: list[tuple[str, str]] = field(default_factory=list)

    def serve_npm(self, package: str, latest: str) -> None:
        encoded = package.replace("/", "%2F")
        self.payloads["registry.npmjs.org", f"/{encoded}"] = {"dist-tags": {"latest": latest}}

    def serve_pypi(self, distribution: str, latest: str) -> None:
        self.payloads["pypi.org", f"/pypi/{distribution}/json"] = {"info": {"version": latest}}

    def serve_ghcr(self, image: str, tags: list[str]) -> None:
        self.payloads["ghcr.io", f"/token?service=ghcr.io&scope=repository:{image}:pull"] = {"token": "anonymous"}
        self.payloads["ghcr.io", f"/v2/{image}/tags/list"] = {"tags": tags}

    def fetch_json(self, host: str, path: str, headers: dict[str, str] | None = None) -> object:
        del headers
        self.requests.append((host, path))
        if (host, path) not in self.payloads:
            failure = f"https://{host}{path}: connection refused"
            raise registries.RegistryLookupError(failure)
        return self.payloads[host, path]


@pytest.fixture
def fake_registry(monkeypatch: pytest.MonkeyPatch) -> FakeRegistry:
    fake = FakeRegistry()
    monkeypatch.setattr(registries, "_fetch_json", fake.fetch_json)
    return fake
