"""Per-entry expiry watches: collect each node's `remove_when`/`remove_how`, probe the conditions as the invoking user, and append a fired watch's instruction to its node's delayed messages (the report's `Action required` block)."""

import os
import pickle
from dataclasses import dataclass

from loguru import logger

from totchef import shell
from totchef.cook_base import CookResult
from totchef.harness import become_user
from totchef.logs import cook_context, inline_mode
from totchef.recipe_graph import build_nodes, node_slice

REMOVE_WHEN_TIMEOUT_SECONDS = 30
GENERIC_REMOVAL_NOTICE = "remove_when satisfied — this entry can be removed from the recipe."


@dataclass(frozen=True)
class RemovalWatch:
    """One node's expiry declaration: the probe that decides removability and the operator instruction to surface once it fires."""

    node_id: str
    condition: str
    instruction: str


def list_removal_watches(config: dict) -> list[RemovalWatch]:
    """Every node's `remove_when` watch, read off the already-validated recipe slices."""
    watches: list[RemovalWatch] = []
    for node_id, node in build_nodes(config).items():
        slice_ = node_slice(config, node)
        condition = slice_.get("remove_when")
        if condition:
            watches.append(RemovalWatch(node_id, condition, slice_.get("remove_how") or GENERIC_REMOVAL_NOTICE))
    return watches


def is_removable(watch: RemovalWatch) -> bool:
    """Probe one watch: exit 0 fires it; non-zero — and any probe failure (no network, missing tool, timeout) — reads as still waiting, so an outage never fabricates a removal notice."""
    with cook_context(watch.node_id):
        try:
            completed = shell.run("bash", "-c", watch.condition, timeout=REMOVE_WHEN_TIMEOUT_SECONDS, note=f"remove_when: {watch.condition}")
        except Exception as exc:
            logger.debug(f"remove_when probe failed: {exc}")
            return False
        if completed.returncode != 0:
            return False
        logger.info(f"remove_when satisfied: {watch.instruction}")
        return True


def find_removable(watches: list[RemovalWatch]) -> list[RemovalWatch]:
    """The watches whose conditions fired, probed as the invoking user — their `gh` auth, their network identity — even when chef itself runs as root: a forked, privilege-dropped child does the probing (in-process when already unprivileged or inline)."""
    if not watches:
        return []
    if inline_mode() or os.geteuid() != 0:
        return [watch for watch in watches if is_removable(watch)]
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            become_user()
            fired = [watch.node_id for watch in watches if is_removable(watch)]
        except Exception:
            fired = []
        with os.fdopen(write_fd, "wb") as out:
            out.write(pickle.dumps(fired))
        os._exit(0)
    os.close(write_fd)
    with os.fdopen(read_fd, "rb") as src:
        payload = src.read()
    os.waitpid(pid, 0)
    fired_ids: list[str] = pickle.loads(payload) if payload else []
    return [watch for watch in watches if watch.node_id in fired_ids]


def append_removal_notices(config: dict, results: dict[str, CookResult]) -> None:
    """Probe every declared watch and append each fired instruction to its node's delayed messages so the `Action required` block names it; a node absent from the results (aborted run) still gets its notice."""
    for watch in find_removable(list_removal_watches(config)):
        result = results.setdefault(watch.node_id, CookResult(watch.node_id, "ok"))
        result.delayed_messages.append(watch.instruction)
