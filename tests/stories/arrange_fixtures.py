"""Arrange half of the prose framework: build the recipe under test and program the system boundaries (bash, network, host, home) a test sets up before acting. The doubles inherit their assertion half from assert_fixtures."""

import platform
import shlex
import subprocess
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from assert_fixtures import HttpAssertions, TerminalAssertions
from totchef import harness, shell
from totchef import terminal as terminal_module
from totchef.registry import cook_registry


class RecipeBuilder:
    """The recipe.toml under test, assembled one section at a time. `declares` adds a subtable entry (`bash.deep_sleep`) when given a name, or a plain-data section (`apt_pkg`) when given only fields."""

    def __init__(self) -> None:
        self.config: dict = {}

    def declares(self, section: str, name: str | None = None, **fields) -> "RecipeBuilder":
        target = self.config.setdefault(section, {})
        if name is None:
            target.update(fields)
        else:
            target[name] = fields
        return self


class ConcurrencyProbe:
    """Observe how many tracked operations are in flight at once. Arm a barrier of `parties` and each tracked op blocks until that many are simultaneously in flight, so a test proves *real* overlap deterministically: a serialized implementation can never gather `parties` together, each op waits alone, times out, and the recorded `max_inflight` stays at 1."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._inflight = 0
        self.max_inflight = 0
        self._barrier: threading.Barrier | None = None

    def arm(self, parties: int, timeout: float = 2.0) -> None:
        """Require `parties` operations to be in flight together; a tracked op that waits alone past `timeout` gives up rather than hanging the test."""
        self._barrier = threading.Barrier(parties, timeout=timeout)

    @contextmanager
    def track(self) -> Generator[None]:
        with self._lock:
            self._inflight += 1
            self.max_inflight = max(self.max_inflight, self._inflight)
        try:
            if self._barrier is not None:
                try:
                    self._barrier.wait()
                except threading.BrokenBarrierError:
                    pass  # serialized: the expected overlap never gathered, max_inflight tells the story
            yield
        finally:
            with self._lock:
                self._inflight -= 1


@dataclass
class RanCommand:
    """One command the system handed to the bash boundary."""

    argv: list[str]
    stdin: bytes | str | None
    streamed: bool

    @property
    def line(self) -> str:
        return shlex.join(self.argv)


@dataclass
class Response:
    match: str
    output: str
    exit_code: int
    effect: Callable[[], None] | None = None


class FakeTerminal(TerminalAssertions):
    """Stands in for `totchef.shell`: the single bash chokepoint. Arrange a command's reply with `arrange`, then verify interactions with `expect_ran`/`expect_not_ran` (the assertion half). Matching is substring against the shell-joined command, so an absolute binary path (`~/.cargo/bin/cargo install --list`) still matches `"cargo install --list"`. A later `arrange` for the same match wins, so a probe re-run after a change can report the new state."""

    def __init__(self) -> None:
        self.commands: list[RanCommand] = []
        self._responses: list[Response] = []
        self.concurrency = ConcurrencyProbe()
        self._concurrent_matches: tuple[str, ...] = ()

    def expect_concurrent(self, *matches: str, parties: int, timeout: float = 2.0) -> "FakeTerminal":
        """Expect every command matching one of `matches` to run concurrently with the others — `parties` of them in flight at once. Use for a cook that fans work across a thread pool (e.g. `uv tool install`/`upgrade`); non-matching commands (a serial probe) run normally."""
        self._concurrent_matches = matches
        self.concurrency.arm(parties, timeout)
        return self

    @property
    def max_concurrent_commands(self) -> int:
        return self.concurrency.max_inflight

    def _concurrency_ctx(self, line: str):
        if self._concurrent_matches and any(match in line for match in self._concurrent_matches):
            return self.concurrency.track()
        return nullcontext()

    def arrange(self, match: str, output: str = "", *, exit_code: int = 0, effect: Callable[[], None] | None = None) -> "FakeTerminal":
        """Arrange the reply for any command matching `match`: its stdout and exit code (default success). `exit_code != 0` makes a `check=True` call raise, a `pre_hook` guard skip, an install hard-fail, etc. `effect` is a side effect a *successful* command has on the world — an installer dropping a binary, say — run after the command so the next probe sees it."""
        self._responses.append(Response(match, output, exit_code, effect))
        return self

    def _respond(self, argv: list[str]) -> Response:
        line = shlex.join(argv)
        for response in reversed(self._responses):
            if response.match in line:
                return response
        return Response("", "", 0)

    def run(
        self,
        *cmd: str,
        stdin: bytes | str | None = None,
        text: bool = True,
        check: bool = False,
        timeout: float | None = None,
        note: str = "",
    ) -> subprocess.CompletedProcess:
        argv = list(cmd)
        self.commands.append(RanCommand(argv, stdin, streamed=False))
        with self._concurrency_ctx(shlex.join(argv)):
            response = self._respond(argv)
            stdout: str | bytes = response.output if text else response.output.encode()
            empty: str | bytes = "" if text else b""
            if check and response.exit_code != 0:
                raise subprocess.CalledProcessError(response.exit_code, argv, output=stdout)
            if response.effect:
                response.effect()
            return subprocess.CompletedProcess(argv, response.exit_code, stdout=stdout, stderr=empty)

    def stream(
        self,
        cmd: list[str],
        tag: str = "",
        *,
        note: str = "",
        stdin: bytes | None = None,
        check: bool = True,
    ) -> None:
        self.commands.append(RanCommand(list(cmd), stdin, streamed=True))
        with self._concurrency_ctx(shlex.join(cmd)):
            response = self._respond(list(cmd))
            if check and response.exit_code != 0:
                raise subprocess.CalledProcessError(response.exit_code, cmd)
            if response.effect:
                response.effect()

    def reset(self) -> None:
        """Forget every arrangement and recorded command — for a test that runs a second, independent scenario through the same patched boundary."""
        self.commands.clear()
        self._responses.clear()


@dataclass
class HttpResponse:
    match: str
    body: bytes


class _Reply:
    """The context-manager object `fetch_url` expects back from `urlopen` (`with urlopen(req) as r: r.read()`)."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_Reply":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


class FakeHttp(HttpAssertions):
    """Stands in for `harness.urlopen`, the single network chokepoint every `fetch_url` call funnels through. Arrange a URL's body with `arrange(url_match, body)`; an un-programmed URL raises, so no test reaches the real network. Verify interactions with `expect_fetched(match)` (the assertion half). Matching is substring against the requested URL."""

    def __init__(self) -> None:
        self.requests: list[str] = []
        self._responses: list[HttpResponse] = []
        self.concurrency = ConcurrencyProbe()

    def expect_concurrent(self, parties: int, timeout: float = 2.0) -> "FakeHttp":
        """Expect `parties` fetches to be in flight at once — for a probe pass that looks up latest versions across a thread pool (crates.io, PyPI)."""
        self.concurrency.arm(parties, timeout)
        return self

    @property
    def max_concurrent_requests(self) -> int:
        return self.concurrency.max_inflight

    def arrange(self, match: str, body: bytes | str) -> "FakeHttp":
        """Arrange the body returned for any URL matching `match`."""
        self._responses.append(HttpResponse(match, body.encode() if isinstance(body, str) else body))
        return self

    def urlopen(self, request: object, *args: object, **kwargs: object) -> _Reply:
        url = str(getattr(request, "full_url", request))
        self.requests.append(url)
        with self.concurrency.track():
            for response in self._responses:
                if response.match in url:
                    return _Reply(response.body)
        raise AssertionError(f"unexpected HTTP GET {url!r}; arrange it with http.arrange({url!r}, ...)")


class FakeSystem:
    """Stands in for the host: which binaries are discoverable and which OS release is running. The machine starts bare (no tools) so a cook needing one hits its real missing-tool path; `has(...)` drops an executable on PATH for `find_binary`/`shutil.which` to find. `running_release(...)` sets the codename apt_repo substitutes into `{release}` (default `noble`)."""

    def __init__(self, bin_dir: Path) -> None:
        self.bin_dir = bin_dir
        self.release = "noble"

    def has(self, *binaries: str) -> "FakeSystem":
        """Make each binary discoverable on PATH (and as a real installer side effect, e.g. `effect=lambda: system.has("bun")`)."""
        for name in binaries:
            executable = self.bin_dir / name
            executable.write_text("#!/bin/sh\n")
            executable.chmod(0o755)
        return self

    def running_release(self, codename: str) -> "FakeSystem":
        self.release = codename
        return self


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
    """Redirect `$HOME` to a temp dir so `Path.home()` (and `~`) land there, isolating per-user cooks from the real home. Also scrub env vars holding an absolute path into the real home (e.g. `BUN_INSTALL`), which would otherwise leak past the `$HOME` redirect."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("BUN_INSTALL", raising=False)
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


@pytest.fixture(autouse=True)
def fresh_runner_colors() -> Generator[None]:
    """Per-cook log/report colors are assigned into a module-global dict in first-seen order (the palette wraps once exhausted); reset it around every test so assignments don't leak across tests — otherwise the cumulative count decides which hue a cook gets."""
    terminal_module._runner_colors.clear()
    yield
    terminal_module._runner_colors.clear()


@pytest.fixture
def recipe() -> RecipeBuilder:
    return RecipeBuilder()


@pytest.fixture
def scenario() -> Callable[[], RecipeBuilder]:
    """Arrange an independent recipe with its own fresh builder — for a test that exercises several distinct recipes (e.g. a few ways a dependency can be malformed). Hand the built recipe to `chef` to run it."""
    return RecipeBuilder


@pytest.fixture
def register_plugin(monkeypatch: pytest.MonkeyPatch) -> Callable[[str, str], None]:
    """Register a fake third-party cook under the `totchef.cooks` entry-point group, exactly as an installed plugin distribution would — so a story can observe its `plugin:<dist>` origin via `--list-cooks` without building and installing a real package."""
    from totchef import registry
    from totchef.cooks.bash_cook import BashCook

    real_entry_points = registry.entry_points

    def register(section: str, dist: str) -> None:
        plugin = SimpleNamespace(
            name=section,
            value=f"{dist}.cooks:Cook",
            dist=SimpleNamespace(name=dist),
            load=lambda: BashCook,
        )
        monkeypatch.setattr(registry, "entry_points", lambda group: [*real_entry_points(group=group), plugin])
        registry.cook_registry.cache_clear()

    return register
