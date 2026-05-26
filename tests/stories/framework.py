"""The fixture framework's machinery. Tests never import this — they receive `recipe`, `terminal`, and `totchef` as fixtures (wired in conftest.py) and read as prose. The only thing mocked is bash execution (totchef.shell); everything else is the real chef.

Collaborators:
- `RecipeBuilder` — the operator's recipe.toml, built up declaratively.
- `FakeTerminal` — the bash boundary: programs what a command prints, records what was run, asserts on it. Stands in for `totchef.shell`.
- `FakeHttp` — the network boundary. Stands in for `harness.urlopen`.
- `FakeSystem` — the host boundary: which binaries are discoverable (`find_binary`/`shutil.which`) and the running OS release codename (apt_repo). The machine starts bare so a cook that needs a tool hits its real "missing tool" path; `has(...)` provisions one.
- `Totchef` — the user action (`plan`/`up`/`lint`), driving the real chef in-process (no fork, no sudo) and returning a `RunReport` to assert against.
"""

import shlex
import subprocess
import textwrap
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from graphlib import TopologicalSorter

from loguru import logger

from totchef.cli import cook_node, print_report
from totchef.cook_base import CookResult
from totchef.cook_runner import run_cook
from totchef.harness import SOFT_FAIL_EXIT
from totchef.recipe_graph import build_node_graph, build_nodes
from totchef.schema_lint import validate


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


class FakeTerminal:
    """Stands in for `totchef.shell`: the single bash chokepoint. Arrange a command's reply with `arrange`, then verify interactions with `expect_ran`/`expect_not_ran`. Matching is substring against the shell-joined command, so an absolute binary path (`~/.cargo/bin/cargo install --list`) still matches `"cargo install --list"`. A later `arrange` for the same match wins, so a probe re-run after a change can report the new state."""

    def __init__(self) -> None:
        self.commands: list[RanCommand] = []
        self._responses: list[Response] = []

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
        response = self._respond(list(cmd))
        if check and response.exit_code != 0:
            raise subprocess.CalledProcessError(response.exit_code, cmd)
        if response.effect:
            response.effect()

    def expect_ran(self, match: str) -> None:
        assert any(match in command.line for command in self.commands), f"expected a command matching {match!r}, but only ran:\n{self._ran_lines()}"

    def expect_not_ran(self, match: str) -> None:
        offenders = [command.line for command in self.commands if match in command.line]
        assert not offenders, f"expected no command matching {match!r}, but ran:\n" + "\n".join(f"  {line}" for line in offenders)

    def reset(self) -> None:
        """Forget every arrangement and recorded command — for a test that runs a second, independent scenario through the same patched boundary."""
        self.commands.clear()
        self._responses.clear()

    def count(self, match: str) -> int:
        """How many run/stream commands matched `match` — for asserting a step ran exactly once (a bootstrap) or fanned out per package."""
        return sum(match in command.line for command in self.commands)

    def stdin_for(self, match: str) -> bytes | str | None:
        """The stdin piped to the first command matching `match` — e.g. the installer script piped into `bash -s`, or the key bytes piped into `gpg --dearmor`."""
        return next((command.stdin for command in self.commands if match in command.line), None)

    def _ran_lines(self) -> str:
        return "\n".join(f"  {command.line}" for command in self.commands) or "  (nothing)"


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


class FakeHttp:
    """Stands in for `harness.urlopen`, the single network chokepoint every `fetch_url` call funnels through. Arrange a URL's body with `arrange(url_match, body)`; an un-programmed URL raises, so no test reaches the real network. Verify interactions with `expect_fetched(match)`. Matching is substring against the requested URL."""

    def __init__(self) -> None:
        self.requests: list[str] = []
        self._responses: list[HttpResponse] = []

    def arrange(self, match: str, body: bytes | str) -> "FakeHttp":
        """Arrange the body returned for any URL matching `match`."""
        self._responses.append(HttpResponse(match, body.encode() if isinstance(body, str) else body))
        return self

    def urlopen(self, request: object, *args: object, **kwargs: object) -> _Reply:
        url = str(getattr(request, "full_url", request))
        self.requests.append(url)
        for response in self._responses:
            if response.match in url:
                return _Reply(response.body)
        raise AssertionError(f"unexpected HTTP GET {url!r}; arrange it with http.arrange({url!r}, ...)")

    def expect_fetched(self, match: str) -> None:
        assert any(match in url for url in self.requests), f"expected a fetch matching {match!r}, but only fetched: {self.requests or '(nothing)'}"


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


@dataclass
class RunReport:
    """What `plan`/`up` produced: the chef's per-node results, plus assertion helpers phrased as the operator's expectations."""

    results: dict[str, CookResult]
    exit_code: int
    report: str = ""
    logs: str = ""
    rows: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for result in self.results.values():
            for row in result.rows:
                self.rows[cook_node(result.cook, row.name)] = row.action

    def assert_report(self, expected: str) -> None:
        """Assert the whole rendered report (the real `print_report` TOON, captured from the logs) matches `expected`, ignoring surrounding blank lines and uniform indentation so the snapshot can be written flush under the call."""
        actual = self.report.strip("\n")
        wanted = textwrap.dedent(expected).strip("\n")
        assert actual == wanted, f"report mismatch:\n--- expected ---\n{wanted}\n--- actual ---\n{actual}"

    def assert_shows(self, node: str, action: str) -> None:
        assert node in self.rows, f"no report row for {node!r}; saw {sorted(self.rows)}"
        assert self.rows[node] == action, f"expected {node!r} to show {action!r}, but it showed {self.rows[node]!r}"

    def assert_logged(self, snippet: str) -> None:
        """Assert a line the operator would see scrolled past — a cook's guidance ("launch the app once"), a failure reason, a "Writing" notice — was logged during the run."""
        assert snippet in self.logs, f"expected a log line containing {snippet!r}, but the run logged:\n{self.logs or '(nothing)'}"

    def assert_succeeded(self) -> None:
        assert self.exit_code == 0, f"expected success (exit 0), got exit {self.exit_code}"

    def assert_soft_failed(self) -> None:
        assert self.exit_code == SOFT_FAIL_EXIT, f"expected soft failure (exit {SOFT_FAIL_EXIT}), got exit {self.exit_code}"

    def assert_hard_failed(self) -> None:
        assert self.exit_code == 1, f"expected hard failure (exit 1), got exit {self.exit_code}"


class RecipeRejected(Exception):
    """Raised by `Totchef.lint` when validation rejects the recipe, carrying the message the operator would see."""


class Totchef:
    """The user action. `plan`/`up`/`lint` drive the real chef against the current recipe, in-process: topo-sort the DAG and run each node directly (no fork, no privilege drop — the bash boundary is mocked, so nothing escalates)."""

    def __init__(self, recipe: RecipeBuilder, terminal: FakeTerminal) -> None:
        self.recipe = recipe
        self.terminal = terminal

    def plan(self) -> RunReport:
        return self._run(dry_run=True)

    def up(self) -> RunReport:
        return self._run(dry_run=False)

    def lint(self) -> None:
        try:
            validate(self.recipe.config)
        except SystemExit as exit:
            raise RecipeRejected(str(exit.code)) from exit

    def _run(self, dry_run: bool) -> RunReport:
        config = self.recipe.config
        validate(config)
        nodes = build_nodes(config)
        order = list(TopologicalSorter(build_node_graph(nodes)).static_order())

        lines: list[str] = []
        sink = logger.add(lambda message: lines.append(message.record["message"]), format="{message}", level="INFO")
        results: dict[str, CookResult] = {}
        try:
            for node_id in order:
                try:
                    result = run_cook(nodes[node_id], config, dry_run)
                except Exception:
                    result = CookResult(node_id, "hard_fail", [], traceback.format_exc())
                results[node_id] = result
                if result.status == "hard_fail":
                    break  # chef aborts the apply on a hard failure
        finally:
            logger.remove(sink)

        report = _capture_report(results, dry_run, "Plan" if dry_run else "Report")
        return RunReport(results, _exit_code(results), report=report, logs="\n".join(lines))


def _capture_report(results: dict[str, CookResult], dry_run: bool, title: str) -> str:
    """Run the real `print_report` and capture the TOON it logs, by attaching a temporary loguru sink around it — so the snapshot is exactly what an operator sees, not a reconstruction."""
    lines: list[str] = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), format="{message}", level="INFO")
    try:
        print_report(results, dry_run, title=title)
    finally:
        logger.remove(sink)
    return "\n".join(lines)


def _exit_code(results: dict[str, CookResult]) -> int:
    if any(result.status == "hard_fail" for result in results.values()):
        return 1
    if any(result.status == "soft_fail" for result in results.values()):
        return SOFT_FAIL_EXIT
    return 0
