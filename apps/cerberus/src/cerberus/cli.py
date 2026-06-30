from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, override

import typer
from rich.console import Console
from rich.table import Table
from typer.core import TyperGroup

from cerberus import __version__, checks, config, context
from cerberus.context import Context
from cerberus.model import CheckResult, Repo, Scope, Status


class LinterGroup(TyperGroup):
    """Make `cerberus [PATH]` lint (ESLint-style) while keeping the named commands.

    A bare invocation, a path, or an option falls through to the `lint` command;
    a known subcommand (`list`, `version`, `lint`) dispatches normally.
    """

    default_command = "lint"

    @override
    def parse_args(self, ctx: Any, args: list[str]) -> list[str]:
        if not args:
            args = [self.default_command]
        elif args[0] not in self.commands and args[0] not in ("--help", "-h"):
            args = [self.default_command, *args]
        return super().parse_args(ctx, args)


app = typer.Typer(
    cls=LinterGroup,
    no_args_is_help=False,
    add_completion=False,
    help="Lint a repo checkout against org invariants.",
)

console = Console()
err = Console(stderr=True)

_GLYPH = {
    Status.PASS: "[green]✓[/green]",
    Status.SKIP: "[dim]○[/dim]",
    Status.FAIL: "[red]✗[/red]",
    Status.ERROR: "[magenta]‼[/magenta]",
}

ConfigOpt = Annotated[Path | None, typer.Option("--config", help="Path to a cerberus.toml.")]
CheckOpt = Annotated[list[str] | None, typer.Option("--check", help="Limit to named check(s).")]


def _select_checks(only: list[str] | None) -> list[checks.Check]:
    if not only:
        return list(checks.ALL)
    selected = []
    for cid in only:
        if cid not in checks.BY_ID:
            raise typer.BadParameter(f"unknown check `{cid}` (known: {', '.join(checks.BY_ID)})")
        selected.append(checks.BY_ID[cid])
    return selected


def _run_check(check: checks.Check, repo: Repo, ctx: Context) -> CheckResult:
    try:
        return check.run(repo, ctx)
    except Exception as exc:  # one check must not abort the whole run
        crashed = CheckResult(check.id, repo.name)
        crashed.error(f"check crashed: {exc}")
        return crashed


def _failed(results: list[CheckResult]) -> bool:
    return any(result.status.rank >= Status.FAIL.rank for result in results)


@app.command()
def version() -> None:
    """Print the cerberus version."""
    console.print(__version__)


@app.command(name="list")
def list_checks() -> None:
    """List every check, its scope, and what it verifies."""
    table = Table(title="cerberus checks")
    table.add_column("id", no_wrap=True)
    table.add_column("scope")
    table.add_column("verifies")
    scope_label = {
        Scope.CONTENT: "content",
        Scope.GIT_HISTORY: "git-history",
    }
    for chk in checks.ALL:
        table.add_row(chk.id, scope_label[chk.scope], chk.summary)
    console.print(table)


@app.command()
def lint(
    path: Annotated[
        Path, typer.Argument(help="Repo checkout to lint (default: current directory).")
    ] = Path("."),
    config_path: ConfigOpt = None,
    check: CheckOpt = None,
    fix: Annotated[bool, typer.Option("--fix", help="Auto-fix fixable problems in place.")] = False,
) -> None:
    """Lint a repository checkout against org invariants.

    Exits non-zero on any FAIL or ERROR, so it drops straight into CI like any
    linter. `--fix` rewrites what it can (trailing whitespace) and leaves the
    rest to report. A repo opts out of checks via `[tool.cerberus] disable` in
    its pyproject.toml.
    """
    ctx = context.local_context(config.load(config_path), path, fix=fix)
    repo = ctx.repos()[0]
    selected = _select_checks(check)

    disabled = config.repo_disabled_checks(path)
    unknown = disabled - set(checks.BY_ID)
    if unknown:
        err.print(f"[yellow]unknown disabled checks ignored: {', '.join(sorted(unknown))}[/yellow]")
    active = [chk for chk in selected if chk.id not in disabled]

    results = [_run_check(chk, repo, ctx) for chk in active]

    _render_lint(repo, results, sorted(disabled & set(checks.BY_ID)))
    if _failed(results):
        raise typer.Exit(code=1)


def _render_lint(repo: Repo, results: list[CheckResult], disabled: list[str]) -> None:
    console.print(f"[bold]{repo.name}[/bold]")
    for check_id in disabled:
        console.print(rf"  {_GLYPH[Status.SKIP]} {check_id}: disabled by \[tool.cerberus]")
    problems = [(r.check, f) for r in results for f in r.problems]
    for check_id, finding in problems:
        console.print(f"  {_GLYPH[finding.status]} {check_id}: {finding.message}")

    if not problems:
        console.print("  [green]✓ all checks pass[/green]")
    else:
        console.print(f"\n[bold]✖ {len(problems)} problems[/bold]")
