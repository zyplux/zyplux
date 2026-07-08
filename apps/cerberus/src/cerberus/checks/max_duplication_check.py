"""Copy-paste duplication cap: cerberus itself runs jscpd over the checkout
and fails when the duplicated-lines percentage exceeds the configured
threshold (`[max_duplication] threshold` in cerberus.toml, default 2%).
jscpd's own exit code carries the verdict — it exits non-zero when the
threshold is exceeded. Cerberus owns the whole jscpd invocation: the file
selection pattern and ignore globs come from `[max_duplication] pattern`
and `ignore` in cerberus.toml, so repos need no `.jscpd.json` of their own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus import proc
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    import subprocess

    from cerberus.context import Context
    from cerberus.model import Repo

ID = "max-duplication"
SUMMARY = "copy-paste duplication across the repo stays under the configured jscpd threshold"
SCOPE = Scope.CONTENT

_VERDICT_MARKER = "ERROR:"


def _verdict(outcome: subprocess.CompletedProcess[str]) -> str | None:
    for line in (outcome.stdout + outcome.stderr).splitlines():
        if _VERDICT_MARKER in line:
            return line.split(_VERDICT_MARKER, 1)[1].strip()
    return None


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    threshold = ctx.config.max_duplication_threshold
    argv = [
        "bunx",
        "jscpd",
        "--threshold",
        str(threshold),
        "--pattern",
        ctx.config.max_duplication_pattern,
        "--ignore",
        ",".join(ctx.config.max_duplication_ignore),
        ".",
    ]
    try:
        outcome = proc.run(argv, cwd=ctx.source.root)
    except proc.ToolNotFoundError as exc:
        res.error(str(exc))
        return res
    if outcome.returncode == 0:
        res.ok(f"duplication is under the {threshold}% jscpd threshold")
        return res
    verdict = _verdict(outcome)
    if verdict is None:
        res.fail(f"jscpd exited {outcome.returncode}; run `{' '.join(argv)}` locally for details")
    else:
        res.fail(verdict)
    return res
