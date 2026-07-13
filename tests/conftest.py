"""Session-wide pytest-xdist plumbing shared by every Python test suite in this workspace."""

from __future__ import annotations

import pytest

NO_XDIST_MARK = "no_xdist"
_CACHE_KEY = "no_xdist/paths"
_session_stash_key: pytest.StashKey[pytest.Session] = pytest.StashKey()


def _is_distributing_controller(config: pytest.Config) -> bool:
    return (
        config.pluginmanager.hasplugin("xdist")
        and not hasattr(config, "workerinput")
        and config.pluginmanager.get_plugin("dsession") is not None
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Every xdist worker is multi-threaded (execnet's own gateway I/O thread), which makes
    fork-family syscalls unsafe there; `no_xdist`-marked items are deselected from every worker
    and re-run serially by `pytest_terminal_summary` below. That serial re-run targets only the
    deferred items' own files rather than the whole suite: collecting everything would import
    token_stats' polars dependency, whose background allocator threads never exit and would
    reintroduce the same fork hazard one step later.
    """
    if not hasattr(config, "workerinput"):
        return
    deferred = [item for item in items if item.get_closest_marker(NO_XDIST_MARK)]
    config.cache.set(_CACHE_KEY, sorted({item.nodeid.split("::", 1)[0] for item in deferred}))
    if not deferred:
        return
    for item in deferred:
        items.remove(item)
    config.hook.pytest_deselected(items=deferred)


def pytest_sessionstart(session: pytest.Session) -> None:
    session.config.stash[_session_stash_key] = session


@pytest.hookimpl(tryfirst=True)
def pytest_terminal_summary(config: pytest.Config) -> None:
    if not _is_distributing_controller(config):
        return
    deferred_paths = config.cache.get(_CACHE_KEY, [])
    if not deferred_paths:
        return
    exit_code = pytest.main([
        *deferred_paths,
        "-o",
        "addopts=--cov=cerberus --cov=clipy --cov=totchef --cov=token_stats --cov-report=term-missing",
        "-p",
        "no:xdist",
        "-q",
        "--cov-append",
        "-m",
        NO_XDIST_MARK,
    ])
    if exit_code != 0:
        config.stash[_session_stash_key].exitstatus = exit_code
