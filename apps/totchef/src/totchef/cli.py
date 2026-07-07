"""totchef CLI: find the recipe, re-exec as root for an apply, run the cooks, report. Exit codes: 0 ok, 75 soft fail, 1 hard fail (aborts)."""

import os
import sys
import time
import tomllib
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from toon_format import encode

from totchef import __version__, harness, registry
from totchef.cook_base import CookResult, ReportRow
from totchef.cook_runner import format_duration, run_recipe
from totchef.harness import SOFT_FAIL_EXIT
from totchef.logs import SHARED_LOG_ENV, drain_logs, inline_mode, set_terminal_echo, start_logging, write_log
from totchef.recipe import RECIPE_ENV, find_cooks_dir, find_files_dir, find_recipe, resolve_explicit, save_recipe, try_find_recipe
from totchef.recipe_types import RecipeConfig
from totchef.removal_watch import append_removal_notices
from totchef.schema_lint import validate
from totchef.terminal import show_table

app = typer.Typer(
    name="totchef",
    no_args_is_help=True,
    add_completion=False,
    help="Hand it a recipe.toml; it makes the machine comply. Idempotent, declarative system configuration.",
)

RecipeOption = Annotated[
    Path | None,
    typer.Option("--recipe", "-r", help="Recipe file or repo dir (default: a recognized name from the cwd up, then a recipe pinned by `totchef init`)."),
]


def prepare(explicit: Path | None) -> Path:
    """Resolve the recipe and pin its sibling assets dir (totchef_files/) and custom-cooks dir (totchef_cooks/), so cooks read bundled sources and the registry sees recipe-local cooks before validation and the run."""
    path = find_recipe(explicit)
    harness.set_files_dir(find_files_dir(path))
    registry.set_recipe_cooks_dir(find_cooks_dir(path))
    return path


def ensure_root(recipe_path: Path) -> None:
    """Re-exec under sudo if not root, pinning the already-resolved recipe and the shared log path across the boundary (sudo sets SUDO_USER, which become_user drops back to). Run the program by its absolute `sys.executable` so sudo's secure_path can't fail to find it: a frozen single-file binary IS that executable, so only the user's args (argv[1:]) follow it; a plain Python invocation runs the interpreter over the script (argv[0]) and its args."""
    if os.geteuid() == 0:
        return
    os.environ[RECIPE_ENV] = str(recipe_path)
    relaunch = [sys.executable, *sys.argv[1:]] if getattr(sys, "frozen", False) else [sys.executable, *sys.argv]
    os.execvp("sudo", ["sudo", f"--preserve-env={SHARED_LOG_ENV},{RECIPE_ENV}", *relaunch])


def load_recipe(recipe_path: Path) -> RecipeConfig:
    with recipe_path.open("rb") as f:
        return tomllib.load(f)


def cook_node(node_id: str, name: str) -> str:
    """The report's identity column: the owning cook (recipe section) dotted with the entry, matching the `section.entry` ids in the logs (e.g. `apt_pkg.code`, `url.rustup`)."""
    return f"{node_id.split('.', 1)[0]}.{name}"


def summary_rows(unchanged: int, elapsed: float | None) -> list[dict[str, str]]:
    """The report's footer rows (under a divider): how many resources were left untouched and the total wall-clock — empty when there's nothing to total."""
    if not unchanged and elapsed is None:
        return []
    return [
        {
            "cook-node": f"{unchanged} unchanged" if unchanged else "elapsed",
            "before": "",
            "current": "",
            "latest": "",
            "action": format_duration(elapsed) if elapsed is not None else "",
        }
    ]


def report_row(node_id: str, row: ReportRow) -> dict[str, str]:
    """One report row as the flat dict the table/TOON render from: the cook-node identity plus its before/current/latest/action cells (past, present, target, verb)."""
    return {"cook-node": cook_node(node_id, row.name), "before": row.before, "current": row.current, "latest": row.latest, "action": row.action}


def log_report_block(
    all_rows: list[dict[str, str]], shown_rows: list[dict[str, str]], summary: list[dict[str, str]], title: str, nothing_changed: str
) -> None:
    """Inline mode records the report to the log file as a structured block: the full node table (every row, including unchanged) and the terse view an operator sees, between sentinels so it can be read back machine-cleanly."""
    full = encode(all_rows) if all_rows else ""
    terse = encode(shown_rows + summary) if shown_rows else nothing_changed
    write_log(f"##totchef-report##\ntitle={title}\n##full##\n{full}\n##shown##\n{terse}\n##end##\n")


def print_report(results: dict[str, CookResult], dry_run: bool, title: str = "Report", elapsed: float | None = None) -> None:
    rows = [(result.cook, row) for result in results.values() for row in result.rows]
    shown = rows if dry_run else [(node_id, row) for node_id, row in rows if row.changed or row.status != "ok"]
    summary = summary_rows(len(rows) - len(shown), elapsed)
    shown_rows = [report_row(node_id, row) for node_id, row in shown]
    suffix = f" ({format_duration(elapsed)})" if elapsed is not None else ""
    nothing_changed = f"=== {title}: nothing changed{suffix} ==="

    if inline_mode():
        log_report_block([report_row(node_id, row) for node_id, row in rows], shown_rows, summary, title, nothing_changed)

    if shown:
        show_table(shown_rows, title=title, summary=summary)
    else:
        logger.info(nothing_changed)

    delayed_rows = [{"cook-node": result.cook, "message": message} for result in results.values() for message in result.delayed_messages]
    if delayed_rows:
        show_table(delayed_rows, title="Action required")


def preview_plan(config: RecipeConfig) -> None:
    """Before a real run, print the plan table to the terminal from a probe-only pass; the probe's cook logs go to the file only, so the terminal shows just the table."""
    set_terminal_echo(False)
    results = run_recipe(config, dry_run=True)
    drain_logs()
    set_terminal_echo(True)
    print_report(results, dry_run=True, title="Plan")


def apply(recipe_path: Path, dry_run: bool) -> None:
    """Load and validate the recipe, then run it; an apply escalates to root and previews the plan first, then reports and signals failures through the exit code. Validation gates every run and comes before escalation and log redirection, so an invalid recipe is rejected loudly on the real stderr without ever prompting for a password; a crash past that point is logged and drained through the pump before exit 1, because a traceback written to the redirected stderr would die with the process."""
    config = load_recipe(recipe_path)
    validate(config)

    if not dry_run and not inline_mode():
        ensure_root(recipe_path)
    log_file = start_logging()
    logger.info(f"=== totchef {__version__} ===")
    drain_logs()
    set_terminal_echo(not dry_run)
    start = time.monotonic()

    try:
        if not dry_run:
            preview_plan(config)

        results = run_recipe(config, dry_run)
        append_removal_notices(config, results)
        drain_logs()
        set_terminal_echo(True)
        print_report(results, dry_run, elapsed=time.monotonic() - start)

        hard = [r.cook for r in results.values() if r.status == "hard_fail"]
        soft = [r.cook for r in results.values() if r.status == "soft_fail"]
        for result in results.values():
            if result.status == "hard_fail" and result.message:
                logger.error(f"[{result.cook}] {result.message}")
        if hard:
            logger.error(f"=== Hard failures: {', '.join(hard)} — apply aborted; full log: {log_file} ===")
            drain_logs()
            raise typer.Exit(1)
        if soft:
            logger.warning(f"=== Soft failures: {', '.join(soft)} (scroll back; full log: {log_file}) ===")
            drain_logs()
            raise typer.Exit(SOFT_FAIL_EXIT)
        drain_logs()
    except typer.Exit:
        raise
    except Exception:
        set_terminal_echo(True)
        logger.exception("=== Crashed outside any cook — a totchef bug, not a recipe failure ===")
        drain_logs()
        raise typer.Exit(1) from None


@app.command()
def up(recipe: RecipeOption = None) -> None:
    """Apply the recipe, converging the system to it (escalates to root)."""
    apply(prepare(recipe), dry_run=False)


@app.command()
def plan(recipe: RecipeOption = None) -> None:
    """Dry-run: probe and print what would change. No root, no changes."""
    apply(prepare(recipe), dry_run=True)


@app.command()
def lint(recipe: RecipeOption = None) -> None:
    """Validate the recipe against the cook schemas and exit. No root, no changes."""
    path = prepare(recipe)
    validate(load_recipe(path))
    typer.echo(f"{path}: valid")


@app.command()
def where(recipe: RecipeOption = None) -> None:
    """Print the recipe path totchef would use and exit."""
    typer.echo(find_recipe(recipe))


@app.command()
def init(
    recipe: Annotated[Path | None, typer.Argument(help="Recipe file or repo directory to pin; omit to use the one discovered here.")] = None,
) -> None:
    """Pin a recipe so `totchef up` finds it from anywhere — saves its path to ~/.config/totchef/config.toml. A symlinked path is pinned as given (not dereferenced), so repointing the symlink later moves the pin without rerunning init."""
    if recipe is not None:
        path = resolve_explicit(recipe, follow_symlinks=False)
    else:
        path = try_find_recipe()
        if path is None:
            raise SystemExit("ERROR: no recipe found here to pin; pass a path: totchef init PATH")
        if not typer.confirm(f"Pin {path} as your default recipe?", default=True):
            raise typer.Exit()
    config = save_recipe(path)
    typer.echo(f"Pinned {path} ({config})")


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"totchef {__version__}")
        raise typer.Exit()


def list_cooks_callback(value: bool) -> None:
    """Print every resolvable cook — section, scope (root/user), and origin (built-in / plugin:<dist> / local:<path>) — as TOON, then exit. Best-effort resolves a recipe so its totchef_cooks/ plugins are listed too."""
    if value:
        if (path := try_find_recipe()) is not None:
            registry.set_recipe_cooks_dir(find_cooks_dir(path))
        rows = [
            {"section": section, "scope": "root" if entry.needs_root else "user", "origin": entry.origin}
            for section, entry in sorted(registry.cook_registry().items())
        ]
        typer.echo(encode(rows))
        raise typer.Exit()


@app.callback()
def root(
    _version: Annotated[bool, typer.Option("--version", callback=version_callback, is_eager=True, help="Show the version and exit.")] = False,
    _list_cooks: Annotated[
        bool,
        typer.Option(
            "--list-cooks", callback=list_cooks_callback, is_eager=True, help="List every resolvable cook and the recipe section it serves, then exit."
        ),
    ] = False,
) -> None:
    pass


def main() -> None:
    app()


if __name__ == "__main__":
    main()
