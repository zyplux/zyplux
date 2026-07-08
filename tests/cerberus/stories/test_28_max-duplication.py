from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.context import Context
    from cerberus.model import CheckResult, Finding, Repo, Status

type RunCheck = Callable[[str, Repo, Context], CheckResult]
type MakeContext = Callable[..., Context]
type RunMaxDuplication = Callable[..., CheckResult]

CHECK_ID = "max-duplication"

_OVER_THRESHOLD_OUTPUT = (
    "Found 104 clones.\nERROR: jscpd found too many duplicates (14.1%) over threshold (2.0%)\ntime: 199ms\n"
)
_CUSTOM_THRESHOLD_TOML = 'default_recipe_marker = "just --list"\n\n[max_duplication]\nthreshold = 5\n'
_CUSTOM_SELECTION_TOML = (
    'default_recipe_marker = "just --list"\n\n'
    "[max_duplication]\n"
    'pattern = "**/*.rs"\n'
    'ignore = ["**/target/**"]\n'
)
_DEFAULT_PATTERN = "**/*.{ts,tsx,py}"
_DEFAULT_IGNORE = (
    "**/node_modules/**,**/dist/**,**/.venv/**,**/coverage/**,**/reference_clones/**,**/graphify-out/**"
)


def _argv(threshold: str = "2", pattern: str = _DEFAULT_PATTERN, ignore: str = _DEFAULT_IGNORE) -> list[str]:
    return ["bunx", "jscpd", "--threshold", threshold, "--pattern", pattern, "--ignore", ignore, "."]


class ProcDouble(Protocol):
    """The shape of the subprocess test double `fake_proc` hands back.

    A structural type, not a nominal import of the concrete class conftest.py
    builds — keeps this file free of any dependency on where that class lives.
    """

    calls: list[tuple[list[str], Path | None]]

    def serve(self, tool: str, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None: ...
    def serve_missing(self, tool: str) -> None: ...


@pytest.fixture
def run_max_duplication(
    repo: Repo, ctx: Context, run_check: RunCheck, make_context: MakeContext, tmp_path: Path
) -> RunMaxDuplication:
    def _run(*, config_toml: str | None = None) -> CheckResult:
        if config_toml is None:
            return run_check(CHECK_ID, repo, ctx)
        config_path = tmp_path / "cerberus.toml"
        config_path.write_text(config_toml)
        return run_check(CHECK_ID, repo, make_context(Path(), config_path=config_path))

    return _run


def test_28_1_1_passes_when_jscpd_stays_under_the_duplication_threshold(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd")
    result = run_max_duplication()
    assert result.findings == [finding(status.PASS, "duplication is under the 2% jscpd threshold")]


def test_28_1_2_fails_with_jscpds_verdict_when_the_threshold_is_exceeded(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd", returncode=1, stdout=_OVER_THRESHOLD_OUTPUT)
    result = run_max_duplication()
    assert result.findings == [finding(status.FAIL, "jscpd found too many duplicates (14.1%) over threshold (2.0%)")]


def test_28_1_3_fails_with_the_exit_code_when_jscpd_emits_no_verdict_line(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd", returncode=3)
    result = run_max_duplication()
    assert result.findings == [
        finding(status.FAIL, f"jscpd exited 3; run `{' '.join(_argv())}` locally for details")
    ]


def test_28_1_4_errors_when_bunx_is_not_on_path(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve_missing("bunx")
    result = run_max_duplication()
    assert result.findings == [finding(status.ERROR, "`bunx` not found on PATH")]


def test_28_2_1_runs_jscpd_at_the_repo_root_with_the_default_selection_and_threshold(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble
) -> None:
    fake_proc.serve("jscpd")
    run_max_duplication()
    assert fake_proc.calls == [(_argv(), Path())]


def test_28_2_2_passes_a_configured_threshold_through_to_jscpd(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble, finding: type[Finding], status: type[Status]
) -> None:
    fake_proc.serve("jscpd")
    result = run_max_duplication(config_toml=_CUSTOM_THRESHOLD_TOML)
    assert fake_proc.calls == [(_argv(threshold="5"), Path())]
    assert result.findings == [finding(status.PASS, "duplication is under the 5% jscpd threshold")]


def test_28_2_3_passes_a_configured_pattern_and_ignore_through_to_jscpd(
    run_max_duplication: RunMaxDuplication, fake_proc: ProcDouble
) -> None:
    fake_proc.serve("jscpd")
    run_max_duplication(config_toml=_CUSTOM_SELECTION_TOML)
    assert fake_proc.calls == [(_argv(pattern="**/*.rs", ignore="**/target/**"), Path())]
