#!/usr/bin/env -S uv run
"""Orchestrator for `just up`: re-exec as root, parse recipe.toml into a graph, run the cooks, report. Exit codes: 0 ok, 75 soft fail, 1 hard fail (aborts)."""

import os
import sys
import tomllib

import typer
from loguru import logger

from cook_base import CookResult
from cook_runner import run_recipe
from harness import RECIPE_TOML, SOFT_FAIL_EXIT
from logs import SHARED_LOG_ENV, drain_logs, start_logging
from schema_lint import validate
from terminal import show_table


def ensure_root() -> None:
    """Re-exec under sudo if not root, preserving argv and the shared log path (sudo sets SUDO_USER, which become_user drops back to)."""
    if os.geteuid() == 0:
        return
    os.execvp(
        "sudo",
        ["sudo", f"--preserve-env={SHARED_LOG_ENV}", sys.executable, *sys.argv],
    )


def print_report(results: dict[str, CookResult], dry_run: bool) -> None:
    all_rows = [row for result in results.values() for row in result.rows]
    changed_rows = [r for r in all_rows if r.changed or r.status != "ok"]
    shown = all_rows if dry_run else changed_rows

    logger.info("")
    if shown:
        show_table(
            [
                {
                    "name": r.name,
                    "mgr": r.manager,
                    "installed": r.installed,
                    "latest": r.latest,
                    "action": r.action,
                }
                for r in shown
            ],
            title="Report",
        )
    else:
        logger.info("=== Report: nothing changed ===")

    if not dry_run:
        unchanged = len(all_rows) - len(changed_rows)
        if unchanged:
            logger.info(f"{unchanged} item(s) unchanged. Run with --dry-run for the full inventory.")


def main(
    dry_run: bool = typer.Option(False, "--dry-run", help="Probe only; print the report without acting."),
    lint: bool = typer.Option(
        False,
        "--lint",
        help="Validate recipe.toml against the cook schemas and exit; no root, no changes.",
    ),
) -> None:
    if lint:
        with RECIPE_TOML.open("rb") as f:
            validate(tomllib.load(f))
        logger.info(f"{RECIPE_TOML.name}: valid")
        return

    if not dry_run:
        ensure_root()
    start_logging()

    with RECIPE_TOML.open("rb") as f:
        config = tomllib.load(f)
    validate(config)

    results = run_recipe(config, dry_run)
    drain_logs()
    print_report(results, dry_run)

    hard = [r.cook for r in results.values() if r.status == "hard_fail"]
    soft = [r.cook for r in results.values() if r.status == "soft_fail"]
    for result in results.values():
        if result.status == "hard_fail" and result.message:
            logger.error(f"[{result.cook}] {result.message}")
    if hard:
        logger.error(f"=== Hard failures: {', '.join(hard)} — `just up` aborted ===")
        drain_logs()
        raise typer.Exit(1)
    if soft:
        logger.warning(f"=== Soft failures: {', '.join(soft)} (scroll back) ===")
        drain_logs()
        raise typer.Exit(SOFT_FAIL_EXIT)
    drain_logs()


if __name__ == "__main__":
    typer.run(main)
