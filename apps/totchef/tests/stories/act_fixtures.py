"""Act half of the prose framework: drive totchef the way a user does — the real `totchef plan`/`up`/`lint` command, in-process, through nothing but its public CLI. Inline mode (TOTCHEF_INLINE) runs every cook in this process so the system-boundary doubles arranged in arrange_fixtures still apply; the report is read back from what the command printed and the log file it wrote."""

from collections.abc import Callable
from pathlib import Path

import pytest
import tomli_w
from typer.testing import CliRunner

from arrange_fixtures import RecipeBuilder
from assert_fixtures import CliResult, LintReport, RunReport
from totchef.cli import app  # the public CLI entrypoint — the one production handle a test is allowed

REPORT_MARKER = "##totchef-report##"


def _section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[-1].split(end, 1)[0].strip("\n")


def _last_report(log_text: str) -> tuple[str, str]:
    """The full node table and the terse operator view from the run's last report block (an `up` logs the preview plan first, then the converging report — the last block is the one that ran)."""
    if REPORT_MARKER not in log_text:
        return "", ""
    block = log_text.rsplit(REPORT_MARKER, 1)[-1]
    return _section(block, "##full##", "##shown##"), _section(block, "##shown##", "##end##")


class Totchef:
    """The user action: run a real `totchef <command>` against the recipe under test. `plan`/`up` converge (or preview) and hand back a RunReport read from the command's output and log; `lint` validates and reports whether the recipe was accepted."""

    def __init__(self, recipe: RecipeBuilder, workdir: Path) -> None:
        self.recipe = recipe
        self.workdir = workdir
        self._runner = CliRunner()
        self._runs = 0

    def plan(self) -> RunReport:
        result, log_text = self._invoke("plan", color=True)
        return self._report(result, log_text)

    def up(self) -> RunReport:
        result, log_text = self._invoke("up", color=True)
        return self._report(result, log_text)

    def lint(self) -> LintReport:
        """Drive `totchef lint` and hand back what it decided: validated, or rejected with the operator-facing message."""
        result, _ = self._invoke("lint")
        return LintReport(rejected=result.exit_code != 0, message=result.output)

    def _report(self, result: CliResult, log_text: str) -> RunReport:
        full_table, terse = _last_report(log_text)
        return RunReport(
            exit_code=result.exit_code,
            report=terse,
            logs=result.stderr,
            terminal_report=result.stdout,
            full_table=full_table,
        )

    def _invoke(self, command: str, color: bool = False) -> tuple[CliResult, str]:
        """Write the recipe to a fresh TOML file and run `totchef <command>` against it in inline mode (no fork, no sudo), capturing stdout, stderr, exit code, and the log file it wrote."""
        self._runs += 1
        recipe_path = self.workdir / f"recipe-{self._runs}.toml"
        recipe_path.write_text(tomli_w.dumps(self.recipe.config))
        log_file = self.workdir / f"run-{self._runs}.log"
        env = {"TOTCHEF_INLINE": "1", "TOTCHEF_LOG_FILE": str(log_file)}
        if color:
            env["FORCE_COLOR"] = "1"
        outcome = self._runner.invoke(app, [command, "--recipe", str(recipe_path)], env=env, color=color, catch_exceptions=False)
        log_text = log_file.read_text() if log_file.exists() else ""
        return CliResult(outcome.stdout, outcome.exit_code, stderr=outcome.stderr), log_text


@pytest.fixture
def totchef(recipe: RecipeBuilder, tmp_path: Path) -> Totchef:
    return Totchef(recipe, tmp_path)


class Cli:
    """The operator's command line: invoke a real `totchef <command>` (the informational ones — `where`, `lint`, `--version`, `--list-cooks`) and capture what scrolled past plus the exit code. The recipe-discovery commands read the arranged filesystem/env, so a test sets those up and observes the path the CLI resolves."""

    def __init__(self) -> None:
        self._runner = CliRunner()

    def run(self, *args: str, stdin: str | None = None) -> CliResult:
        outcome = self._runner.invoke(app, list(args), input=stdin)
        return CliResult(outcome.stdout, outcome.exit_code, stderr=outcome.stderr)


@pytest.fixture
def cli() -> Cli:
    return Cli()


@pytest.fixture
def chef(tmp_path: Path) -> Callable[[RecipeBuilder], Totchef]:
    """Run totchef against an independently arranged recipe — for a test that exercises several distinct recipes (e.g. a few ways a dependency can be malformed) against the same mocked system. Pairs with `scenario`, which arranges those recipes."""

    def run(recipe: RecipeBuilder) -> Totchef:
        return Totchef(recipe, tmp_path)

    return run
