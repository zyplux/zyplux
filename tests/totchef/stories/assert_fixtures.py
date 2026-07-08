"""Assert half of the prose framework: the run report, plus assertion mixins for the system-boundary doubles. No production imports."""

import json
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    # Deferred to a type-only import: arrange_fixtures imports HttpAssertions/TerminalAssertions
    # from this module at runtime, so an eager import here would be circular.
    from arrange_fixtures import RanCommand

    type JsonValue = dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None

SOFT_FAIL_EXIT = 75  # totchef's public soft-failure exit code (stories §1.1.3) — asserted as a contract, not imported
MIN_NODE_ROW_FIELDS = (
    2  # a data row is `node,before,current,latest,action`; identity + outcome need at least this many comma-fields
)


class TerminalAssertions:
    """Assertion half of the bash double: verifies what the system handed to the shell. The arrange half (FakeTerminal) records each command into `commands`."""

    commands: list[RanCommand]

    def expect_ran(self, match: str) -> None:
        assert any(match in command.line for command in self.commands), (
            f"expected a command matching {match!r}, but only ran:\n{self._ran_lines()}"
        )

    def expect_not_ran(self, match: str) -> None:
        offenders = [command.line for command in self.commands if match in command.line]
        assert not offenders, f"expected no command matching {match!r}, but ran:\n" + "\n".join(
            f"  {line}" for line in offenders
        )

    def count(self, match: str) -> int:
        """How many run/stream commands matched `match` — for asserting a step ran exactly once (a bootstrap) or fanned out per package."""
        return sum(match in command.line for command in self.commands)

    def stdin_for(self, match: str) -> bytes | str | None:
        """The stdin piped to the first command matching `match` — e.g. an installer script piped into `bash -s`, or key bytes piped into `gpg --dearmor`."""
        return next((command.stdin for command in self.commands if match in command.line), None)

    def cwd_for(self, match: str) -> Path | None:
        """The working dir the first command matching `match` ran in — e.g. piped to `bash` from `$HOME` so a relative bin dir resolves under `~`."""
        return next((command.cwd for command in self.commands if match in command.line), None)

    def _ran_lines(self) -> str:
        return "\n".join(f"  {command.line}" for command in self.commands) or "  (nothing)"


class HttpAssertions:
    """Assertion half of the network double: verifies what was fetched. The arrange half (FakeHttp) records URLs and each timeout."""

    requests: list[str]
    timeouts: list[object]

    def expect_fetched(self, match: str) -> None:
        assert any(match in url for url in self.requests), (
            f"expected a fetch matching {match!r}, but only fetched: {self.requests or '(nothing)'}"
        )

    def expect_bounded_timeouts(self) -> None:
        """Every fetch must carry a positive timeout, so a stalled upstream raises instead of hanging the probe/run forever."""
        message = f"every fetch must pass a positive timeout; got: {self.timeouts or '(no fetches)'}"
        assert self.timeouts, message
        assert all(isinstance(t, (int, float)) and t > 0 for t in self.timeouts), message


@dataclass
class LintReport:
    """What `lint` produced: whether the recipe validated, and the message an operator would see. Mirrors how `plan`/`up` return a RunReport."""

    rejected: bool
    message: str = ""

    def assert_valid(self) -> None:
        assert not self.rejected, f"expected the recipe to validate, but lint rejected it:\n{self.message}"

    def assert_rejected(self, snippet: str = "") -> None:
        """Assert the operator's recipe is refused at lint, optionally carrying `snippet` in the message that tells them how to fix it."""
        assert self.rejected, "expected the recipe to be rejected at lint, but it validated"
        assert snippet in self.message, (
            f"recipe was rejected, but the message {self.message!r} did not mention {snippet!r}"
        )


SGR_CODES = {
    "green": "32",
    "yellow": "33",
    "red": "31",
    "red bold": "1;31",
    "dim": "2",
}


def _parse_node_rows(full_table: str) -> dict[str, str]:
    """Map cook-node -> action from the log's full TOON table. Skips the header and blank lines; a row is `node,before,current,latest,action`."""
    rows: dict[str, str] = {}
    for line in full_table.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("[", "{", "#")):
            continue
        fields = [field.strip().strip('"') for field in stripped.split(",")]
        if len(fields) >= MIN_NODE_ROW_FIELDS:
            rows[fields[0]] = fields[-1]
    return rows


@dataclass
class RunReport:
    """What `plan`/`up` showed: the terse `report`, the scrolled `logs`, the colored `terminal_report`, and the log file's `full_table`."""

    exit_code: int
    report: str = ""
    logs: str = ""
    terminal_report: str = ""
    full_table: str = ""
    rows: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.rows = _parse_node_rows(self.full_table)

    def assert_shows(self, node: str, action: str) -> None:
        assert node in self.rows, f"no report row for {node!r}; saw {sorted(self.rows)}"
        assert self.rows[node] == action, f"expected {node!r} to show {action!r}, but it showed {self.rows[node]!r}"

    def assert_ran_before(self, earlier: str, later: str) -> None:
        """Assert the report lists `earlier` above `later`: the applied order, so a dependency shows resolved before the resource needing it."""
        order = list(self.rows)
        assert earlier in order, f"no report row for {earlier!r}; saw {order}"
        assert later in order, f"no report row for {later!r}; saw {order}"
        assert order.index(earlier) < order.index(later), (
            f"expected {earlier!r} to run before {later!r}, but the report ordered them {order}"
        )

    def assert_colored(self, text: str, color: str) -> None:
        """Assert that on a terminal the report renders `text` in `color` (the operator sees a color-coded table, not the plain TOON in `report`)."""
        needle = f"\x1b[{SGR_CODES[color]}m{text}"
        assert needle in self.terminal_report, (
            f"expected {text!r} colored {color!r} in the terminal report, but got:\n{self.terminal_report!r}"
        )

    def assert_logged(self, snippet: str) -> None:
        """Assert a line the operator would see scrolled past — guidance, a failure reason, or a "Writing" notice — was logged during the run."""
        assert snippet in self.logs, (
            f"expected a log line containing {snippet!r}, but the run logged:\n{self.logs or '(nothing)'}"
        )

    def assert_succeeded(self) -> None:
        assert self.exit_code == 0, f"expected success (exit 0), got exit {self.exit_code}"

    def assert_rejected(self, snippet: str = "") -> None:
        """Assert the run was refused at validation — nonzero exit carrying `snippet` in the lint message, mirroring LintReport.assert_rejected."""
        refusal = self.terminal_report + self.logs
        assert self.exit_code != 0, "expected the run to be rejected at validation, but it exited 0"
        assert snippet in refusal, f"run was rejected, but the message {refusal!r} did not mention {snippet!r}"

    def assert_soft_failed(self) -> None:
        assert self.exit_code == SOFT_FAIL_EXIT, (
            f"expected soft failure (exit {SOFT_FAIL_EXIT}), got exit {self.exit_code}"
        )

    def assert_hard_failed(self) -> None:
        assert self.exit_code == 1, f"expected hard failure (exit 1), got exit {self.exit_code}"


@dataclass
class CliResult:
    """What a `totchef <command>` showed: stdout, stderr, exit code. `output` is both together, as a terminal would scroll them."""

    stdout: str
    exit_code: int
    stderr: str = ""

    @property
    def output(self) -> str:
        return self.stdout + self.stderr

    def assert_succeeded(self) -> None:
        assert self.exit_code == 0, f"command exited {self.exit_code}:\n{self.output}"

    def assert_failed(self) -> None:
        assert self.exit_code != 0, f"expected the command to fail, but it exited 0:\n{self.output}"

    def assert_prints(self, snippet: str) -> None:
        assert snippet in self.output, (
            f"expected the output to contain {snippet!r}, but it printed:\n{self.output or '(nothing)'}"
        )

    def assert_output(self, expected: str) -> None:
        """Assert the whole output matches `expected`, a full snapshot. Ignores blank lines/indentation so it can sit flush under the call."""
        actual = self.output.strip("\n")
        wanted = textwrap.dedent(expected).strip("\n")
        assert actual == wanted, f"output mismatch:\n--- expected ---\n{wanted}\n--- actual ---\n{actual}"

    def assert_lists(self, section: str, *, scope: str = "", origin: str = "") -> None:
        """Assert the listing has a row for `section` with scope/origin — for text with a run-varying value a full snapshot can't pin."""
        line = next((line for line in self.output.splitlines() if section in line), None)
        assert line is not None, f"expected a row for {section!r}, but it listed:\n{self.output}"
        assert scope in line, f"expected {section!r} to list scope {scope!r}, but its row was {line!r}"
        assert origin in line, f"expected {section!r} to list origin {origin!r}, but its row was {line!r}"


@pytest.fixture
def read_json() -> Callable[[Path], JsonValue]:
    """Read a config file a cook produced and parse it as data, so a test asserts on the resulting values, not the exact formatting an implementation emits."""

    def read(path: Path) -> JsonValue:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    return read
