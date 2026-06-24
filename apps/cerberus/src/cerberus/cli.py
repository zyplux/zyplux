from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table
from typer.core import TyperGroup

from cerberus import __version__, checks, config, context
from cerberus.context import Context
from cerberus.model import CheckResult, Repo, Scope, Status
from cerberus.source import parse_org_ref


class LinterGroup(TyperGroup):
    """Make `cerberus [PATH]` lint (ESLint-style) while keeping the named commands.

    A bare invocation, a path, or an option falls through to the `lint` command;
    a known subcommand (`org`, `list`, `version`, `lint`) dispatches normally.
    """

    default_command = "lint"

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
    help="Lint a repo against org invariants; `cerberus org <ORG>` scans a whole org.",
)

console = Console()
err = Console(stderr=True)

_GLYPH = {
    Status.PASS: "[green]✓[/green]",
    Status.SKIP: "[dim]○[/dim]",
    Status.WARN: "[yellow]●[/yellow]",
    Status.FAIL: "[red]✗[/red]",
    Status.ERROR: "[magenta]‼[/magenta]",
}

ConfigOpt = Annotated[Path | None, typer.Option("--config", help="Path to a cerberus.toml.")]
RepoOpt = Annotated[list[str] | None, typer.Option("--repo", "-r", help="Limit to repo(s).")]
CheckOpt = Annotated[list[str] | None, typer.Option("--check", help="Limit to named check(s).")]
OrgArg = Annotated[
    str, typer.Argument(metavar="ORG", help="GitHub org: bare name, github.com/<org>, or full URL.")
]


def _select_repos(ctx: Context, only: list[str] | None) -> list[Repo]:
    repos = ctx.repos()
    if only:
        wanted = set(only)
        repos = [r for r in repos if r.name in wanted]
        missing = wanted - {r.name for r in repos}
        if missing:
            err.print(f"[yellow]unknown repos ignored: {', '.join(sorted(missing))}[/yellow]")
    return repos


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


_LOCAL_SKIP = {Scope.CONTROL_PLANE: "evaluated by `cerberus org` (needs admin API)"}
_ORG_SKIP = {Scope.GIT_HISTORY: "evaluated by `cerberus lint` (needs the checkout's git history)"}


def _run_in_mode(
    check: checks.Check, repo: Repo, ctx: Context, skip_reasons: dict[Scope, str]
) -> CheckResult:
    reason = skip_reasons.get(check.scope)
    if reason is not None:
        skipped = CheckResult(check.id, repo.name)
        skipped.skip(reason)
        return skipped
    return _run_check(check, repo, ctx)


def _evaluate(
    ctx: Context, repos: list[Repo], selected: list[checks.Check]
) -> dict[str, dict[str, CheckResult]]:
    return {
        repo.name: {check.id: _run_in_mode(check, repo, ctx, _ORG_SKIP) for check in selected}
        for repo in repos
    }


def _failed(results: list[CheckResult]) -> bool:
    return any(result.status.rank >= Status.FAIL.rank for result in results)


def _matrix_failed(matrix: dict[str, dict[str, CheckResult]]) -> bool:
    return _failed([r for row in matrix.values() for r in row.values()])


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
        Scope.CONTROL_PLANE: "control-plane",
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

    Control-plane checks (rulesets, secret provisioning) are skipped here — they
    live in `cerberus org` because the checkout cannot see them. Exits non-zero
    on any FAIL or ERROR (warnings do not fail the run), so it drops straight
    into CI like any linter. `--fix` rewrites what it can (trailing whitespace)
    and leaves the rest to report.
    """
    ctx = context.local_context(config.load(config_path), path, fix=fix)
    repo = ctx.repos()[0]
    selected = _select_checks(check)

    results = [_run_in_mode(chk, repo, ctx, _LOCAL_SKIP) for chk in selected]

    _render_lint(repo, results)
    if _failed(results):
        raise typer.Exit(code=1)


def _render_lint(repo: Repo, results: list[CheckResult]) -> None:
    console.print(f"[bold]{repo.name}[/bold]")
    problems = [(r.check, f) for r in results for f in r.problems]
    for check_id, finding in problems:
        console.print(f"  {_GLYPH[finding.status]} {check_id}: {finding.message}")

    if not problems:
        console.print("  [green]✓ all checks pass[/green]")
    else:
        fails = sum(1 for _, f in problems if f.status.rank >= Status.FAIL.rank)
        warns = sum(1 for _, f in problems if f.status is Status.WARN)
        console.print(
            f"\n[bold]✖ {len(problems)} problems ({fails} failures, {warns} warnings)[/bold]"
        )


@app.command(name="org")
def org_scan(
    org: OrgArg,
    config_path: ConfigOpt = None,
    repo: RepoOpt = None,
    check: CheckOpt = None,
) -> None:
    """Scan every repo in ORG and report findings per repo.

    Runs all checks, including the control-plane ones the local linter skips.
    Exits non-zero on any FAIL or ERROR (warnings do not fail the run). Needs
    `gh` authenticated with admin scope on the org.
    """
    try:
        login = parse_org_ref(org)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    ctx = context.github_context(replace(config.load(config_path), org=login))
    repos = _select_repos(ctx, repo)
    selected = _select_checks(check)
    matrix = _evaluate(ctx, repos, selected)

    _render_org(repos, selected, matrix)
    if _matrix_failed(matrix):
        raise typer.Exit(code=1)


def _render_org(
    repos: list[Repo], selected: list[checks.Check], matrix: dict[str, dict[str, CheckResult]]
) -> None:
    for repo in repos:
        row = matrix[repo.name]
        console.print(f"\n[bold]{repo.name}[/bold]")
        for chk in selected:
            result = row[chk.id]
            shown = result.problems or [f for f in result.findings if f.status is Status.SKIP]
            if not shown:
                console.print(f"  {_GLYPH[Status.PASS]} {chk.id}")
                continue
            console.print(f"  {_GLYPH[result.status]} {chk.id}")
            for finding in shown:
                console.print(f"      {_GLYPH[finding.status]} {finding.message}")
