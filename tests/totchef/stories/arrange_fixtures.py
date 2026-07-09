(
    """Arrange half of the prose framework: builds the recipe and programs the """
    """bash/network/host/home boundaries; assertions live in assert_fixtures."""
)

import json
import platform
import shlex
import subprocess
import threading
from contextlib import contextmanager, nullcontext, suppress
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, TypedDict, Unpack

import pytest
from assert_fixtures import HttpAssertions, TerminalAssertions
from totchef import __version__, harness, registry, shell
from totchef import terminal as terminal_module
from totchef.cooks import apt_repo_root_cook
from totchef.cooks.bash_cook import BashCook
from totchef.cooks.usr_local_bin_root_cook import UsrLocalBinCook
from totchef.cooks.usr_local_sbin_root_cook import UsrLocalSbinCook

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from contextlib import AbstractContextManager
    from typing import Self

    from act_fixtures import Totchef
    from totchef.recipe_types import RecipeConfig, RecipeValue

CHEZMOI_COOK = (Path(__file__).resolve().parents[3] / "apps/totchef/examples/totchef_cooks/chezmoi_cook.py").read_text()

GIT_NEEDS_INSTALL = (
    "git:\n  Installed: (none)\n  Candidate: 1:2.40\n  Version table:\n     1:2.40 500\n"
    "        500 http://archive noble/main amd64 Packages\n"
)


class RecipeBuilder:
    (
        """The recipe.toml under test, assembled one section at a time. `declares` adds a """
        """subtable entry when given a name, else a plain-data section."""
    )

    def __init__(self) -> None:
        self.config: RecipeConfig = {}

    def declares(self, section: str, name: str | None = None, **fields: RecipeValue) -> RecipeBuilder:
        target = self.config.setdefault(section, {})
        assert isinstance(target, dict)  # declares always seeds a section with a subtable or plain-data dict
        if name is None:
            target.update(fields)
        else:
            target[name] = fields
        return self


class ConcurrencyProbe:
    (
        """How many tracked ops are in flight at once. `arm(parties)` blocks each op until """
        """`parties` overlap, proving concurrency deterministically."""
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._inflight = 0
        self.max_inflight = 0
        self._barrier: threading.Barrier | None = None

    def arm(self, parties: int, timeout: float = 2.0) -> None:
        (
            """Require `parties` operations to be in flight together; a tracked op that waits """
            """alone past `timeout` gives up rather than hanging the test."""
        )
        self._barrier = threading.Barrier(parties, timeout=timeout)

    @contextmanager
    def track(self) -> Generator[None]:
        with self._lock:
            self._inflight += 1
            self.max_inflight = max(self.max_inflight, self._inflight)
        try:
            if self._barrier is not None:
                with suppress(threading.BrokenBarrierError):
                    self._barrier.wait()
            yield
        finally:
            with self._lock:
                self._inflight -= 1


@dataclass
class RanCommand:
    """One command the system handed to the bash boundary."""

    argv: list[str]
    stdin: bytes | str | None
    cwd: Path | None = None
    timeout: float | None = None
    note: str = ""
    tag: str = ""

    @property
    def line(self) -> str:
        return shlex.join(self.argv)


@dataclass
class Response:
    match: str
    output: str
    exit_code: int
    effect: Callable[[], None] | None = None


class _RunOptions(TypedDict, total=False):
    (
        """Keyword options `shell.run` accepts, bundled as one `**options` param — the call """
        """surface is fixed by production, not this file."""
    )

    stdin: bytes | str | None
    text: bool
    check: bool
    timeout: float | None
    note: str
    cwd: Path | None


class _StreamOptions(TypedDict, total=False):
    (
        """The keyword-only options `totchef.shell.stream` accepts beyond `cmd`/`tag`, bundled """
        """for the same reason as `_RunOptions`."""
    )

    note: str
    stdin: bytes | None
    check: bool
    cwd: Path | None


class FakeTerminal(TerminalAssertions):
    (
        """Stands in for `totchef.shell`. `arrange` programs a reply; `expect_ran`/`expect_not_ran` """
        """verify it. Matching is substring; later `arrange` wins."""
    )

    def __init__(self) -> None:
        self.commands: list[RanCommand] = []
        self._responses: list[Response] = []
        self.concurrency = ConcurrencyProbe()
        self._concurrent_matches: tuple[str, ...] = ()

    def expect_concurrent(self, *matches: str, parties: int, timeout: float = 2.0) -> FakeTerminal:
        (
            """Expect commands matching one of `matches` to run concurrently — `parties` in """
            """flight at once. Non-matching commands run normally."""
        )
        self._concurrent_matches = matches
        self.concurrency.arm(parties, timeout)
        return self

    @property
    def max_concurrent_commands(self) -> int:
        return self.concurrency.max_inflight

    def _concurrency_ctx(self, line: str) -> AbstractContextManager[None]:
        if self._concurrent_matches and any(match in line for match in self._concurrent_matches):
            return self.concurrency.track()
        return nullcontext()

    def arrange(
        self, match: str, output: str = "", *, exit_code: int = 0, effect: Callable[[], None] | None = None
    ) -> FakeTerminal:
        (
            """Arrange the reply for commands matching `match`: stdout and exit code. `effect` """
            """runs after success, e.g. an installer dropping a binary."""
        )
        self._responses.append(Response(match, output, exit_code, effect))
        return self

    def _respond(self, argv: list[str]) -> Response:
        line = shlex.join(argv)
        for response in reversed(self._responses):
            if response.match in line:
                return response
        return Response("", "", 0)

    def run(self, *cmd: str, **options: Unpack[_RunOptions]) -> subprocess.CompletedProcess[str | bytes]:
        argv = list(cmd)
        stdin = options.get("stdin")
        text = options.get("text", True)
        check = options.get("check", False)
        timeout = options.get("timeout")
        note = options.get("note", "")
        cwd = options.get("cwd")
        self.commands.append(
            RanCommand(argv, stdin, cwd=cwd if cwd is not None else Path.home(), timeout=timeout, note=note)
        )
        with self._concurrency_ctx(shlex.join(argv)):
            response = self._respond(argv)
            stdout: str | bytes = response.output if text else response.output.encode()
            empty: str | bytes = "" if text else b""
            if check and response.exit_code != 0:
                raise subprocess.CalledProcessError(response.exit_code, argv, output=stdout)
            if response.effect:
                response.effect()
            return subprocess.CompletedProcess(argv, response.exit_code, stdout=stdout, stderr=empty)

    def stream(self, cmd: list[str], tag: str = "", **options: Unpack[_StreamOptions]) -> None:
        note = options.get("note", "")
        stdin = options.get("stdin")
        check = options.get("check", True)
        cwd = options.get("cwd")
        self.commands.append(
            RanCommand(list(cmd), stdin, cwd=cwd if cwd is not None else Path.home(), tag=tag, note=note)
        )
        with self._concurrency_ctx(shlex.join(cmd)):
            response = self._respond(list(cmd))
            if check and response.exit_code != 0:
                raise subprocess.CalledProcessError(response.exit_code, cmd)
            if response.effect:
                response.effect()

    def reset(self) -> None:
        (
            """Forget every arrangement and recorded command — for a test that runs a second, """
            """independent scenario through the same patched boundary."""
        )
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

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


class FakeHttp(HttpAssertions):
    (
        """Stands in for `harness.urlopen`. `arrange(match, body)` programs a URL's body; an """
        """un-programmed URL raises. `expect_fetched` verifies by substring."""
    )

    def __init__(self) -> None:
        self.requests: list[str] = []
        self.timeouts: list[object] = []
        self._responses: list[HttpResponse] = []
        self.concurrency = ConcurrencyProbe()

    def expect_concurrent(self, parties: int, timeout: float = 2.0) -> FakeHttp:
        (
            """Expect `parties` fetches to be in flight at once — for a probe pass that looks """
            """up latest versions across a thread pool (crates.io, PyPI)."""
        )
        self.concurrency.arm(parties, timeout)
        return self

    @property
    def max_concurrent_requests(self) -> int:
        return self.concurrency.max_inflight

    def arrange(self, match: str, body: bytes | str) -> FakeHttp:
        """Arrange the body returned for any URL matching `match`."""
        self._responses.append(HttpResponse(match, body.encode() if isinstance(body, str) else body))
        return self

    def urlopen(self, request: object, *args: object, **kwargs: object) -> _Reply:
        url = str(getattr(request, "full_url", request))
        self.requests.append(url)
        self.timeouts.append(kwargs.get("timeout", args[1] if len(args) > 1 else None))
        with self.concurrency.track():
            for response in self._responses:
                if response.match in url:
                    return _Reply(response.body)
        message = f"unexpected HTTP GET {url!r}; arrange it with http.arrange({url!r}, ...)"
        raise AssertionError(message)


class FakeSystem:
    (
        """Stands in for the host: discoverable binaries and OS release. `has(...)` drops an """
        """executable on PATH; `running_release(...)` sets `{release}`."""
    )

    def __init__(self, bin_dir: Path) -> None:
        self.bin_dir = bin_dir
        self.release = "noble"

    def has(self, *binaries: str) -> FakeSystem:
        (
            """Make each binary discoverable on PATH (and as a real installer side effect, e.g. """
            """`effect=lambda: system.has("bun")`)."""
        )
        for name in binaries:
            executable = self.bin_dir / name
            executable.write_text("#!/bin/sh\n")
            executable.chmod(0o755)
        return self

    def running_release(self, codename: str) -> FakeSystem:
        self.release = codename
        return self


GITHUB_TREE_ROOT_SHA = "root0000root0000root0000root0000root0000"


class FakeSkillsRepo:
    (
        """One skills repo behind the bash and network boundaries. `delivers` programs what the """
        """next `skills add <repo>` writes; `upstream_holds`/`upstream_matches` program the """
        """repo's GitHub tree the cook probes before re-syncing."""
    )

    def __init__(self, repo: str, home: Path, terminal: FakeTerminal, http: FakeHttp) -> None:
        self.repo = repo
        self._home = home
        self._terminal = terminal
        self._http = http
        self._delivered: dict[str, str] = {}

    def delivers(
        self,
        *skills: tuple[str, str],
        files: dict[str, dict[str, str]] | None = None,
        synced_at: str = "2026-01-01T00:00:00Z",
    ) -> FakeSkillsRepo:
        (
            """Program the next `skills add <repo>`: `skills` is the full (name, folder_sha) """
            """lockfile state it leaves behind, `files` each skill's own dropped files. The real """
            """CLI rewrites updatedAt (`synced_at`) on every add whether or not content changed; """
            """only the folder sha tracks content."""
        )
        self._delivered = dict(skills)

        def sync() -> None:
            self._write_lockfile(skills, synced_at)
            for name, dropped in (files or {}).items():
                self._drop_files(name, dropped)

        self._terminal.arrange(f"skills add {self.repo}", effect=sync)
        return self

    def upstream_holds(self, *skill_shas: tuple[str, str]) -> FakeSkillsRepo:
        """Program the repo's GitHub trees response: one `skills/<name>` tree entry per (name, folder_sha)."""
        tree = [{"path": f"skills/{name}", "type": "tree", "sha": sha} for name, sha in skill_shas]
        self._http.arrange(
            f"api.github.com/repos/{self.repo}/git/trees/HEAD",
            json.dumps({"sha": GITHUB_TREE_ROOT_SHA, "tree": tree}),
        )
        return self

    def upstream_matches(self) -> FakeSkillsRepo:
        """Program upstream to hold exactly what the last programmed sync delivered — nothing changed on GitHub."""
        return self.upstream_holds(*self._delivered.items())

    def _write_lockfile(self, skills: tuple[tuple[str, str], ...], synced_at: str) -> None:
        entries = {
            name: {
                "source": self.repo,
                "skillFolderHash": folder_sha,
                "updatedAt": synced_at,
                "skillPath": f"skills/{name}/SKILL.md",
            }
            for name, folder_sha in skills
        }
        lock_dir = self._home / ".agents"
        lock_dir.mkdir(parents=True, exist_ok=True)
        (lock_dir / ".skill-lock.json").write_text(json.dumps({"version": 3, "skills": entries}))

    def _drop_files(self, name: str, files: dict[str, str]) -> None:
        (
            """Write a skill's own files the way a symlink-mode `skills add` does: into the """
            """canonical store `~/.agents/skills/<name>`, with `~/.claude/skills/<name>` becoming """
            """a symlink to it (replacing whatever sat there, as the CLI's createSymlink does); """
            """every file arrives non-executable, since git doesn't preserve that bit."""
        )
        skill_dir = self._home / ".agents" / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            dropped = skill_dir / filename
            dropped.write_text(content)
            dropped.chmod(0o644)
        agent_entry = self._home / ".claude" / "skills" / name
        agent_entry.parent.mkdir(parents=True, exist_ok=True)
        if agent_entry.is_symlink():
            agent_entry.unlink()
        elif agent_entry.is_dir():
            for stale in sorted(agent_entry.rglob("*"), reverse=True):
                stale.rmdir() if stale.is_dir() else stale.unlink()
            agent_entry.rmdir()
        agent_entry.symlink_to(skill_dir)


@pytest.fixture(autouse=True)
def terminal(monkeypatch: pytest.MonkeyPatch) -> FakeTerminal:
    (
        """The single mocked bash surface: cooks call `shell.run`/`shell.stream`, so patching """
        """these two names intercepts all bash execution."""
    )
    fake = FakeTerminal()
    monkeypatch.setattr(shell, "run", fake.run)
    monkeypatch.setattr(shell, "stream", fake.stream)
    return fake


@pytest.fixture(autouse=True)
def http(monkeypatch: pytest.MonkeyPatch) -> FakeHttp:
    (
        """The single mocked network surface: `fetch_url` resolves `urlopen` at call time, so """
        """patching `harness.urlopen` intercepts every fetch."""
    )
    fake = FakeHttp()
    monkeypatch.setattr(harness, "urlopen", fake.urlopen)
    return fake


@pytest.fixture
def totchef_version() -> str:
    """The installed distribution's version — the value every run banner and `--version` must state."""
    return __version__


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (
        """Redirect `$HOME` to a temp dir so `Path.home()`/`~` land there. Also scrub """
        """`BUN_INSTALL`/`XDG_*_HOME`, which CI sets and production prefers."""
    )
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    for leaked in ("BUN_INSTALL", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(leaked, raising=False)
    return home_dir


@pytest.fixture(autouse=True)
def system(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeSystem:
    (
        """Isolate the host: PATH is an empty bin dir, so `find_binary` sees only what a test """
        """provisions; the OS release is pinned for apt_repo."""
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir))
    fake = FakeSystem(bin_dir)
    monkeypatch.setattr(platform, "freedesktop_os_release", lambda: {"VERSION_CODENAME": fake.release})
    return fake


@pytest.fixture(autouse=True)
def fresh_registry() -> Generator[None]:
    (
        """Reset the per-run globals each test: the HOME-dependent cook registry, the recipe's """
        """pinned custom-cooks dir, and its pinned assets dir."""
    )
    registry.set_recipe_cooks_dir(None)
    harness.set_files_dir(None)
    registry.cook_registry.cache_clear()
    yield
    registry.set_recipe_cooks_dir(None)
    harness.set_files_dir(None)
    registry.cook_registry.cache_clear()


@pytest.fixture(autouse=True)
def fresh_runner_colors(monkeypatch: pytest.MonkeyPatch) -> None:
    (
        """Per-cook colors are assigned into a module-global dict in first-seen order; reset """
        """before every test so leftovers don't decide a hue."""
    )
    monkeypatch.setattr(terminal_module, "_runner_colors", {})


@pytest.fixture
def usr_local_bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (
        """Point [usr_local_bin]'s /usr/local/bin at a temp dir, isolating system-wide command """
        """installs from the real host."""
    )
    bin_dir = tmp_path / "usr-local-bin"
    monkeypatch.setattr(UsrLocalBinCook, "bin_dir", str(bin_dir))
    return bin_dir


@pytest.fixture
def usr_local_sbin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point [usr_local_sbin]'s /usr/local/sbin at a temp dir, isolating admin-command installs from the real host."""
    bin_dir = tmp_path / "usr-local-sbin"
    monkeypatch.setattr(UsrLocalSbinCook, "bin_dir", str(bin_dir))
    return bin_dir


@pytest.fixture
def apt_keyrings_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point [apt_repo]'s /usr/share/keyrings at a temp dir, isolating keyring installs from the real host."""
    keyrings_dir = tmp_path / "keyrings"
    monkeypatch.setattr(apt_repo_root_cook, "KEYRINGS_DIR", keyrings_dir)
    return keyrings_dir


@pytest.fixture
def apt_sources_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point [apt_repo]'s /etc/apt/sources.list.d at a temp dir, isolating .sources writes from the real host."""
    sources_dir = tmp_path / "sources.list.d"
    monkeypatch.setattr(apt_repo_root_cook, "SOURCES_DIR", sources_dir)
    return sources_dir


@pytest.fixture
def bundled_files(tmp_path: Path) -> Path:
    (
        """The recipe's sibling assets dir (totchef_files/), resolved by the real run from """
        """tmp_path — recipe-relative resolution, not a patched global."""
    )
    files_dir = tmp_path / "totchef_files"
    files_dir.mkdir()
    return files_dir


@pytest.fixture
def custom_cooks(tmp_path: Path) -> Path:
    (
        """The recipe's sibling custom-cooks dir (totchef_cooks/), scanned by the real run for """
        """loose `*_cook.py` plugins beside the recipe."""
    )
    cooks_dir = tmp_path / "totchef_cooks"
    cooks_dir.mkdir()
    return cooks_dir


@pytest.fixture
def chezmoi_cook(custom_cooks: Path) -> Path:
    (
        """Drop the externalized chezmoi cook into totchef_cooks/, so §11 drives it as a """
        """discovered custom cook, not a built-in."""
    )
    target = custom_cooks / "chezmoi_cook.py"
    target.write_text(CHEZMOI_COOK)
    return target


@pytest.fixture
def chezmoi_repo(tmp_path: Path) -> Path:
    (
        """A recipe repo (a recognized name beside totchef_cooks/chezmoi_cook.py), for listing """
        """the cook via plain cwd resolution, no harness."""
    )
    repo = tmp_path / "chezmoi-repo"
    cooks = repo / "totchef_cooks"
    cooks.mkdir(parents=True)
    (repo / "totchef_recipe.toml").write_text("")
    (cooks / "chezmoi_cook.py").write_text(CHEZMOI_COOK)
    return repo


@pytest.fixture
def chezmoi_provisioned(
    system: FakeSystem,
    terminal: FakeTerminal,
    home: Path,
    chezmoi_cook: Path,
    totchef: Totchef,
) -> None:
    (
        """A [chezmoi] recipe already converged — source cloned, config written, capture timer """
        """enabled — with the terminal wiped, so the test's own `up()` is the re-run."""
    )
    del chezmoi_cook
    system.has("chezmoi")
    (home / ".local/share/chezmoi/.git").mkdir(parents=True)
    totchef.recipe.declares("chezmoi", repo="https://github.test/operator/dotfiles.git")
    totchef.up().assert_shows("chezmoi.dotfiles", "applied")
    terminal.reset()


@pytest.fixture
def git_needs_install() -> str:
    """`apt-cache policy git` output for a git that's absent but installable — arranges apt_pkg to plan an install."""
    return GIT_NEEDS_INSTALL


@pytest.fixture
def escalation_probe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[[], list[tuple[str, list[str]]]]:
    (
        """Arm the real no-escalation gate for `cli` runs: calling the probe makes the process """
        """non-root with recipe execution and logging stubbed, and returns the list where any """
        """`os.execvp` re-exec a command attempts would land — it must stay empty."""
    )

    def arm() -> list[tuple[str, list[str]]]:
        escalations: list[tuple[str, list[str]]] = []
        monkeypatch.setattr("os.geteuid", lambda: 1000)
        monkeypatch.setattr("os.execvp", lambda *argv: escalations.append(argv))
        monkeypatch.setattr("totchef.cli.run_recipe", lambda *_args, **_kwargs: {})
        monkeypatch.setattr("totchef.cli.start_logging", lambda _echo_to_terminal=True: nullcontext(tmp_path / "log"))
        monkeypatch.setattr("totchef.cli.drain_logs", lambda: None)
        return escalations

    return arm


@pytest.fixture
def zyp_skills(
    recipe: RecipeBuilder, system: FakeSystem, terminal: FakeTerminal, http: FakeHttp, home: Path
) -> FakeSkillsRepo:
    (
        """The §12 baseline: `[skills]` declares zyplux/zyp-skills and bun/bunx sit on PATH. """
        """Program the repo's boundary behavior on the returned FakeSkillsRepo."""
    )
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    return FakeSkillsRepo("zyplux/zyp-skills", home, terminal, http)


@pytest.fixture
def installed_totchef_skill(zyp_skills: FakeSkillsRepo, totchef: Totchef, home: Path) -> Path:
    (
        """The totchef skill (content id #aaaa1111) already installed from zyplux/zyp-skills by """
        """a converged first `up`. Holds the agent entry `~/.claude/skills/totchef`, a symlink """
        """into the canonical store."""
    )
    zyp_skills.delivers(
        ("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555"),
        files={"totchef": {"SKILL.md": "---\nname: totchef\n---\n"}},
    )
    totchef.up().assert_shows("skills.zyplux/zyp-skills/totchef", "installed")
    return home / ".claude" / "skills" / "totchef"


@pytest.fixture
def recipe() -> RecipeBuilder:
    return RecipeBuilder()


@pytest.fixture
def scenario() -> Callable[[], RecipeBuilder]:
    (
        """Arrange an independent recipe with its own builder, for a test exercising several """
        """recipes malformed differently. Hand it to `chef`."""
    )
    return RecipeBuilder


@pytest.fixture
def register_plugin(monkeypatch: pytest.MonkeyPatch) -> Callable[[str, str], None]:
    (
        """Register a fake third-party cook under `totchef.cooks`, as an installed plugin """
        """would, so a story observes its `plugin:<dist>` origin."""
    )
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
