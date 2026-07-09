from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, override

import typer
from rich.console import Console
from rich.table import Table
from typer.core import TyperGroup

from cerberus import __version__, bites, config, context
from cerberus.graph import build as build_graph
from cerberus.graph import explain_text, query_text
from cerberus.graph import load as load_graph
from cerberus.graph import write as write_graph
from cerberus.model import CheckResult, Repo, Scope, Status

if TYPE_CHECKING:
    import networkx as nx

    from cerberus.context import Context


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
        elif args[0] not in self.commands and args[0] not in {"--help", "-h"}:
            args = [self.default_command, *args]
        return super().parse_args(ctx, args)


app = typer.Typer(
    cls=LinterGroup,
    no_args_is_help=False,
    add_completion=False,
    help="🐺 Lint a repo checkout against org invariants.",
)

console = Console(highlight=False)
err = Console(stderr=True, highlight=False)
logger = logging.getLogger(__name__)

_GLYPH = {
    Status.PASS: "[green]🐾[/green]",
    Status.SKIP: "[dim]○[/dim]",
    Status.FAIL: "[red]💢[/red]",
    Status.ERROR: "[magenta]‼[/magenta]",
}

ConfigOpt = Annotated[Path | None, typer.Option("--config", help="Path to a cerberus.toml.")]
CheckOpt = Annotated[list[str] | None, typer.Option("--check", help="Limit to named bite(s).")]


class _UnknownCheckError(typer.BadParameter):
    def __init__(self, check_id: str) -> None:
        super().__init__(f"unknown bite `{check_id}` (known: {', '.join(bites.BY_ID)})")


def _select_checks(only: list[str] | None) -> list[bites.Check]:
    if not only:
        return list(bites.ALL)
    selected = []
    for cid in only:
        if cid not in bites.BY_ID:
            raise _UnknownCheckError(cid)
        selected.append(bites.BY_ID[cid])
    return selected


def _run_check(check: bites.Check, repo: Repo, ctx: Context) -> CheckResult:
    try:
        return check.run(repo, ctx)
    except Exception as exc:
        logger.exception("bite %s crashed for %s", check.id, repo.name)
        crashed = CheckResult(check.id, repo.name)
        crashed.error(f"bite crashed: {exc}")
        return crashed


def _failed(results: list[CheckResult]) -> bool:
    return any(result.status.rank >= Status.FAIL.rank for result in results)


@app.command()
def version() -> None:
    """Print the cerberus version."""
    console.print(__version__)


@app.command(name="list")
def list_checks() -> None:
    """List every bite, its scope, and what it verifies."""
    table = Table(title="cerberus bites")
    table.add_column("id", no_wrap=True)
    table.add_column("scope")
    table.add_column("verifies")
    scope_label = {
        Scope.CONTENT: "content",
        Scope.GIT_HISTORY: "git-history",
    }
    for chk in bites.ALL:
        table.add_row(chk.id, scope_label[chk.scope], chk.summary)
    console.print(table)


@app.command()
def lint(
    path: Annotated[Path, typer.Argument(help="Repo checkout to lint (default: current directory).")] = Path(),
    config_path: ConfigOpt = None,
    check: CheckOpt = None,
    *,
    fix: Annotated[bool, typer.Option("--fix", help="Auto-fix fixable problems in place.")] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Itemize what each bite measured (clones, dead-code issues).")
    ] = False,
) -> None:
    """Lint a repository checkout against org invariants.

    Exits non-zero on any FAIL or ERROR, so it drops straight into CI like any
    linter. `--fix` rewrites what it can (trailing whitespace) and leaves the
    rest to report. A repo adjusts org defaults via a `cerberus.toml` at its
    root, overlaid key by key onto the bundled configuration; `off = true` in
    a bite's table switches it off entirely, unless `--check` names it.
    """
    ctx = context.local_context(config.load(config_path, repo_root=path), path, fix=fix, verbose=verbose)
    repo = ctx.repos()[0]
    selected = _select_checks(check)

    off = ctx.config.disabled_bites
    unknown_off = off - set(bites.BY_ID)
    if unknown_off:
        err.print(f"[yellow]unknown off bites ignored: {', '.join(sorted(unknown_off))}[/yellow]")
    active = selected if check else [chk for chk in selected if chk.id not in off]

    results = [_run_check(chk, repo, ctx) for chk in active]

    _render_lint(repo, results)
    if _failed(results):
        raise typer.Exit(code=1)


@app.command()
def graph(
    path: Annotated[Path, typer.Argument(help="Repo checkout to graph (default: current directory).")] = Path(),
    out: Annotated[
        Path | None, typer.Option("--out", help="Directory to write graph.json into (default: repo root).")
    ] = None,
) -> None:
    """Build a dependency graph of a repo's own Python and TypeScript source."""
    ctx = context.local_context(config.load(), path)
    repo = ctx.repos()[0]
    result = build_graph(repo, ctx)
    out_dir = out if out is not None else path
    write_graph(result, out_dir)
    console.print(f"wrote {out_dir / 'graph.json'}")


GraphOpt = Annotated[Path, typer.Option("--graph", help="Path to a graph.json built by `cerberus graph`.")]


class _GraphNotFoundError(typer.BadParameter):
    def __init__(self, graph_path: Path) -> None:
        super().__init__(f"graph file not found: {graph_path} (run `cerberus graph` first)")


def _load_graph_or_exit(graph_path: Path) -> nx.DiGraph[str]:
    if not graph_path.is_file():
        raise _GraphNotFoundError(graph_path)
    return load_graph(graph_path)


@app.command(name="graph-explain")
def graph_explain(
    node: Annotated[str, typer.Argument(help="Node id, source path, or label to explain.")],
    graph_path: GraphOpt = Path("graph.json"),
) -> None:
    """Explain a single node from a graph built by `cerberus graph`."""
    console.print(explain_text(_load_graph_or_exit(graph_path), node), markup=False, soft_wrap=True)


@app.command(name="graph-query")
def graph_query(
    question: Annotated[str, typer.Argument(help="Free-text question to seed the traversal.")],
    graph_path: GraphOpt = Path("graph.json"),
    depth: Annotated[int, typer.Option("--depth", help="Traversal depth.")] = 2,
    budget: Annotated[int, typer.Option("--budget", help="Approximate character budget for the output.")] = 2000,
    *,
    dfs: Annotated[bool, typer.Option("--dfs", help="Traverse depth-first instead of breadth-first.")] = False,
) -> None:
    """Traverse a graph built by `cerberus graph`, seeded by a free-text question."""
    graph = _load_graph_or_exit(graph_path)
    console.print(query_text(graph, question, depth=depth, dfs=dfs, budget=budget), markup=False, soft_wrap=True)


def _render_lint(repo: Repo, results: list[CheckResult]) -> None:
    console.print(f"🐺 cerberus v{__version__}")
    console.print(f"[bold]{repo.name}[/bold]")
    problems = [(r.check, f) for r in results for f in r.problems]
    for result in results:
        detail = f" {result.detail}" if result.detail else ""
        if not result.problems:
            if result.status is Status.SKIP:
                reason = "; ".join(f.message for f in result.findings if f.status is Status.SKIP)
                console.print(f"  {_GLYPH[Status.SKIP]} {result.check}: {reason}{detail}")
            else:
                console.print(f"  {_GLYPH[Status.PASS]} {result.check}{detail}")
        else:
            for finding in result.problems:
                headline, _, rest = finding.message.partition("\n")
                console.print(f"  {_GLYPH[finding.status]} {result.check}: {headline}{detail}")
                if rest:
                    console.print(rest)
        for line in result.verbose_lines:
            console.print(line, markup=False)

    if not problems:
        console.print("  [green]🐾 all bites pass[/green]")
    else:
        console.print(f"\n[bold]💢 {len(problems)} problems[/bold]")
