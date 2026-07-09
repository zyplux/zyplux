"""Trusted seam boundary for cerberus's own story tests.

`cerberus.bites.py_test_seam` forbids a story test file from importing
`cerberus` internals beyond the root package's public surface (`__version__`)
and, for cli apps, `cerberus.cli`'s public surface — see that module's
docstring for the exact rule. Only `test_*.py` story files are scanned, and
their `if TYPE_CHECKING:` imports are exempt (mirroring how the TS seam check
trusts an alias target's own imports), so this module — re-exported by
`conftest.py`, the same layout as `tests/totchef/stories` — is the one
sanctioned place a story test's internal-access needs get satisfied. Story
tests import this module's type aliases and double classes only under
`TYPE_CHECKING`, for annotations.

Every fixture below hands back either a ready-made value (a `Repo`, a built
`Context`, a `CheckResult` from actually running a check), a factory for one
(`ok`/`fail`/`skip`/`error` build a `Finding` of that status), or an internal
class/enum itself (`Status`, `Scope`) as a fixture return value — never as
something a story test would need a runtime `import` statement to reach.
Checks are always selected by their id STRING (`bites.BY_ID[check_id]`), so
a story test never names — and therefore never imports — the check submodule
it exercises.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from cerberus import bites, config, context, proc, registries, tool_pins
from cerberus.bites.rumdl_canonical_config_bite import CANONICAL as _RUMDL_CANONICAL
from cerberus.graph import search as _graph_search
from cerberus.model import CheckResult, Finding, Repo, Scope, Status
from cerberus.source import GitHistoryUnavailableError, LocalSource

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    from cerberus.context import Context

type RunCheck = Callable[[str, Repo, Context], CheckResult]
type RunCheckWithFiles = Callable[[str, dict[str, str]], CheckResult]
type RunCheckWithWorkflows = Callable[[str, dict[str, str]], CheckResult]
type RunCheckOnDisk = Callable[..., CheckResult]
type MakeContext = Callable[..., Context]
type RegisterFakeCheck = Callable[[str, Callable[[Repo, Context], CheckResult]], None]
type MakeFinding = Callable[[str], Finding]
type NpmToolSpec = Callable[[str], str]


@pytest.fixture
def repo() -> Repo:
    return Repo("demo")


@pytest.fixture
def ctx() -> Context:
    return context.local_context(config.load(), Path())


@pytest.fixture
def make_context() -> MakeContext:
    def _make(root: Path, *, fix: bool = False, verbose: bool = False, config_path: Path | None = None) -> Context:
        return context.local_context(config.load(config_path), root, fix=fix, verbose=verbose)

    return _make


@pytest.fixture
def run_check() -> RunCheck:
    def _run(check_id: str, repo: Repo, ctx: Context) -> CheckResult:
        return bites.BY_ID[check_id].run(repo, ctx)

    return _run


@pytest.fixture
def run_check_with_files(
    repo: Repo, ctx: Context, run_check: RunCheck, monkeypatch: pytest.MonkeyPatch
) -> RunCheckWithFiles:
    """Run a check by id against virtual file content, keyed by repo-relative path.

    A path absent from `files` reads as "file does not exist" (`None`), same as
    a real repo missing that path. `ctx.paths` is also stubbed to enumerate
    exactly this `files` mapping's keys, for checks that list a directory
    (e.g. discovering workspace packages or story-test files) rather than
    reading one known path.
    """

    def _run(check_id: str, files: dict[str, str]) -> CheckResult:
        monkeypatch.setattr(ctx, "paths", lambda _repo: sorted(files))
        monkeypatch.setattr(ctx, "file", lambda _repo, path: files.get(path))
        return run_check(check_id, repo, ctx)

    return _run


@pytest.fixture
def run_check_with_workflows(
    repo: Repo, ctx: Context, run_check: RunCheck, monkeypatch: pytest.MonkeyPatch
) -> RunCheckWithWorkflows:
    """Run a check by id against virtual workflow content, keyed by workflow file name."""

    def _run(check_id: str, workflows: dict[str, str]) -> CheckResult:
        monkeypatch.setattr(ctx, "workflows", lambda _repo: workflows)
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
        original = bites.BY_ID[check_id]
        fake = bites.Check(original.id, original.summary, original.scope, run)
        monkeypatch.setitem(bites.BY_ID, check_id, fake)

    return _register


@pytest.fixture
def ok() -> MakeFinding:
    return partial(Finding, Status.PASS)


@pytest.fixture
def fail() -> MakeFinding:
    return partial(Finding, Status.FAIL)


@pytest.fixture
def skip() -> MakeFinding:
    return partial(Finding, Status.SKIP)


@pytest.fixture
def error() -> MakeFinding:
    return partial(Finding, Status.ERROR)


@pytest.fixture
def status() -> type[Status]:
    return Status


@pytest.fixture
def check_result() -> type[CheckResult]:
    return CheckResult


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
def graph_search() -> ModuleType:
    return _graph_search


@pytest.fixture
def no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch away the `git` binary so a story test can exercise the git-unavailable path."""
    monkeypatch.setattr(proc.shutil, "which", lambda _tool: None)


@pytest.fixture
def rumdl_canonical() -> str:
    return _RUMDL_CANONICAL


@pytest.fixture
def known_check_ids() -> tuple[str, ...]:
    return tuple(bites.BY_ID)


@pytest.fixture
def npm_tool_pins() -> dict[str, str]:
    return dict(tool_pins.NPM_TOOL_PINS)


@pytest.fixture
def npm_tool_spec() -> NpmToolSpec:
    return tool_pins.format_spec


def _strip_pin(spec: str) -> str:
    name = spec.rpartition("@")[0]
    return name or spec


@dataclass
class FakeProc:
    """An in-memory double for `cerberus.proc`'s single subprocess boundary.

    Outcomes are served per tool — the program a `bunx <tool> ...` invocation
    launches, or `argv[0]` itself for direct invocations; a version-pinned
    spec (`tool@1.2.3`) is served under the bare tool name. A tool that runs
    distinct subcommands can be served per subcommand via a `"tool subcommand"`
    key. `output_files` are written into the directory the invocation names
    after `--output`, mimicking tools that emit report files there.
    `config_snapshots` captures the content of the file each invocation names
    after `--config` — checks write that file into a temp dir that is gone by
    the time a test can look, so the double reads it at call time.
    """

    outcomes: dict[str, subprocess.CompletedProcess[str]] = field(default_factory=dict)
    served_output_files: dict[str, dict[str, str]] = field(default_factory=dict)
    calls: list[tuple[list[str], Path | None]] = field(default_factory=list)
    config_snapshots: list[str] = field(default_factory=list)
    missing: set[str] = field(default_factory=set)

    def serve(
        self,
        tool: str,
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        output_files: dict[str, str] | None = None,
    ) -> None:
        self.outcomes[tool] = subprocess.CompletedProcess([tool], returncode, stdout, stderr)
        if output_files is not None:
            self.served_output_files[tool] = dict(output_files)

    def serve_missing(self, tool: str) -> None:
        self.missing.add(tool)

    def _write_output_files(self, tool: str, argv: list[str]) -> None:
        files = self.served_output_files.get(tool)
        if files is None or "--output" not in argv:
            return
        out_dir = Path(argv[argv.index("--output") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (out_dir / name).write_text(text)

    def _snapshot_config_file(self, argv: list[str]) -> None:
        if "--config" in argv:
            self.config_snapshots.append(Path(argv[argv.index("--config") + 1]).read_text(encoding="utf-8"))

    def run(self, argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(argv), cwd))
        if argv[0] in self.missing:
            raise proc.ToolNotFoundError(argv[0])
        self._snapshot_config_file(argv)
        launched = argv[1:] if argv[0] == "bunx" and len(argv) > 1 else argv
        launched_tool = _strip_pin(launched[0])
        subcommand_key = " ".join([launched_tool, *launched[1:2]])
        tool = subcommand_key if subcommand_key in self.outcomes else launched_tool
        self._write_output_files(tool, argv)
        outcome = self.outcomes[tool]
        return subprocess.CompletedProcess(argv, outcome.returncode, outcome.stdout, outcome.stderr)


@pytest.fixture
def fake_proc(monkeypatch: pytest.MonkeyPatch) -> FakeProc:
    fake = FakeProc()
    monkeypatch.setattr(proc, "run", fake.run)
    return fake


@dataclass
class FakeRegistry:
    """An in-memory double for `cerberus.registries`' single HTTPS boundary."""

    payloads: dict[tuple[str, str], object] = field(default_factory=dict)
    requests: list[tuple[str, str]] = field(default_factory=list)
    not_found: set[tuple[str, str]] = field(default_factory=set)

    def serve_npm(self, package: str, latest: str) -> None:
        encoded = package.replace("/", "%2F")
        self.payloads["registry.npmjs.org", f"/{encoded}"] = {"dist-tags": {"latest": latest}}

    def serve_pypi(self, distribution: str, latest: str) -> None:
        self.payloads["pypi.org", f"/pypi/{distribution}/json"] = {"info": {"version": latest}}

    def serve_ghcr(self, image: str, tags: list[str]) -> None:
        self.payloads["ghcr.io", f"/token?service=ghcr.io&scope=repository:{image}:pull"] = {"token": "anonymous"}
        self.payloads["ghcr.io", f"/v2/{image}/tags/list"] = {"tags": tags}

    def serve_npm_missing(self, package: str) -> None:
        encoded = package.replace("/", "%2F")
        self.not_found.add(("registry.npmjs.org", f"/{encoded}"))

    def serve_pypi_missing(self, distribution: str) -> None:
        self.not_found.add(("pypi.org", f"/pypi/{distribution}/json"))

    def fetch_json(self, host: str, path: str, headers: dict[str, str] | None = None) -> object:
        del headers
        self.requests.append((host, path))
        if (host, path) in self.not_found:
            failure = f"https://{host}{path}: HTTP 404"
            raise registries.RegistryNotFoundError(failure)
        if (host, path) not in self.payloads:
            failure = f"https://{host}{path}: connection refused"
            raise registries.RegistryLookupError(failure)
        return self.payloads[host, path]


@pytest.fixture
def fake_registry(monkeypatch: pytest.MonkeyPatch) -> FakeRegistry:
    fake = FakeRegistry()
    monkeypatch.setattr(registries, "_fetch_json", fake.fetch_json)
    return fake
