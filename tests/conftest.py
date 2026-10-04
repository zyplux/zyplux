"""Session-wide pytest-xdist plumbing shared by every Python test suite in this workspace."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from xdist.workermanage import WorkerController

pytest_plugins = ["pytester"]

NO_XDIST_MARK = "no_xdist"
_WORKER_KEY = "serial_test_ids"
_deferred_stash_key: pytest.StashKey[set[str]] = pytest.StashKey()
_session_stash_key: pytest.StashKey[pytest.Session] = pytest.StashKey()


def _is_distributing_controller(config: pytest.Config) -> bool:
    return (
        config.pluginmanager.hasplugin("xdist")
        and not hasattr(config, "workerinput")
        and config.pluginmanager.get_plugin("dsession") is not None
    )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Every xdist worker is multi-threaded (execnet's own gateway I/O thread), which makes
    fork-family syscalls unsafe there; `no_xdist`-marked items are deselected from every worker
    and re-run serially by `pytest_terminal_summary` below. That serial re-run targets only the
    deferred items' own files rather than the whole suite: collecting everything would import
    token_stats' polars dependency, whose background allocator threads never exit and would
    reintroduce the same fork hazard one step later.
    """
    workeroutput = getattr(config, "workeroutput", None)
    if workeroutput is None:
        return
    deferred = [item for item in items if item.get_closest_marker(NO_XDIST_MARK)]
    workeroutput[_WORKER_KEY] = [item.nodeid for item in deferred]
    if not deferred:
        return
    for item in deferred:
        items.remove(item)
    config.hook.pytest_deselected(items=deferred)


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node: WorkerController) -> None:
    workeroutput = getattr(node, "workeroutput", {})
    node.config.stash[_deferred_stash_key].update(workeroutput.get(_WORKER_KEY, []))


def pytest_sessionstart(session: pytest.Session) -> None:
    session.config.stash[_session_stash_key] = session
    session.config.stash[_deferred_stash_key] = set()


@pytest.hookimpl(tryfirst=True)
def pytest_terminal_summary(config: pytest.Config) -> None:
    if not _is_distributing_controller(config):
        return
    deferred_ids = sorted(config.stash[_deferred_stash_key])
    if not deferred_ids:
        return
    has_coverage = bool(config.getoption("cov_source", default=[])) and not config.getoption("no_cov", default=False)
    coverage_args = ["--cov-reset", "--cov=clipy", "--cov-append"] if has_coverage else ["--no-cov"]
    exit_code = pytest.main([
        *deferred_ids,
        "-n",
        "0",
        "-q",
        *coverage_args,
    ])
    session = config.stash[_session_stash_key]
    if exit_code != pytest.ExitCode.OK or session.exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = exit_code
