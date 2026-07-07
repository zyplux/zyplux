"""Cook execution engine: chef diffs each cook and acts; `run_recipe` topo-sorts the graph and forks every node (user nodes concurrent and privilege-dropped, root nodes serialized)."""

import os
import pickle
import pwd
import re
import time
import traceback
from graphlib import TopologicalSorter

from loguru import logger

from totchef import shell
from totchef.cook_base import CookResult, ReportRow, StateCook, Status, VersionedCook
from totchef.harness import become_user
from totchef.logs import cook_context, inline_mode
from totchef.recipe_graph import (
    Node,
    build_cook,
    build_node_graph,
    build_nodes,
)
from totchef.terminal import progress_region

STATUS_RANK: dict[Status, int] = {"ok": 0, "soft_fail": 1, "hard_fail": 2}


def pick_worst_status(statuses: list[Status]) -> Status:
    if not statuses:
        return "ok"
    return max(statuses, key=lambda s: STATUS_RANK[s])


def format_version(version: str | None) -> str:
    return version if version else "—"


CONTENT_DIGEST = re.compile(r"[0-9a-f]{64}")


def format_state(token: str) -> str:
    """Render a diff token for the report: a sha256 digest as its short content id (#1a2b3c4d), else as-is."""
    return f"#{token[:8]}" if CONTENT_DIGEST.fullmatch(token) else token


def format_duration(seconds: float) -> str:
    """A wall-clock duration in its natural unit, stepping up at each calendar boundary: fractional seconds (4 sig figs) under a minute, then whole minutes+seconds, hours+minutes past an hour, days+hours past a day."""
    if seconds < 60:
        return f"{seconds:.4g}s" if seconds >= 1e-4 else "0s"
    minutes, sec = int(seconds // 60), int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"
    hours, minutes = minutes // 60, minutes % 60
    if hours < 24:
        return f"{hours}h {minutes}m"
    days, hours = hours // 24, hours % 24
    return f"{days}d {hours}h"


def run_pre_hook(snippet: str) -> bool:
    """A `pre_hook` guard: zero exit proceeds, non-zero skips this item (a benign skip, e.g. "browser is running", not a failure)."""
    try:
        shell.stream(["bash", "-c", snippet], note=f"pre_hook: {snippet}")
        return True
    except Exception:
        logger.info("pre_hook not satisfied; skipping")
        return False


def run_post_hook(snippet: str) -> Status:
    """A `post_hook` runs after a successful change; non-zero -> soft failure."""
    try:
        shell.stream(["bash", "-c", snippet], note=f"post_hook: {snippet}")
        return "ok"
    except Exception as exc:
        logger.warning(f"post_hook failed: {exc}")
        return "soft_fail"


def run_versioned(cook: VersionedCook, section: str, dry_run: bool) -> CookResult:
    requested = cook.list_requested()
    installed_before = cook.list_installed()
    latest = cook.find_latest(requested)

    if dry_run:
        rows: list[ReportRow] = []
        for name in requested:
            installed = installed_before.get(name)
            available = latest.get(name)
            if installed is None:
                action, changed = "would install", True
            elif available is None:
                action, changed = "would sync", True
            elif available != installed:
                action, changed = "would upgrade", True
            else:
                action, changed = "up-to-date", False
            rows.append(
                ReportRow(
                    name,
                    installed or "(none)",
                    installed or "(none)",
                    format_version(available),
                    action,
                    changed,
                )
            )
        return CookResult(section, "ok", rows)

    to_install = [n for n in requested if n not in installed_before]
    to_upgrade = [n for n in requested if n in installed_before and (latest.get(n) is None or latest[n] != installed_before[n])]
    pending = set(to_install) | set(to_upgrade)
    pre_hook, post_hook = cook.get_hooks()

    if pending and pre_hook and not run_pre_hook(pre_hook):
        rows = [
            ReportRow(
                name,
                installed_before.get(name) or "(none)",
                installed_before.get(name) or "(none)",
                format_version(latest.get(name)),
                "skipped" if name in pending else "unchanged",
                False,
            )
            for name in requested
        ]
        return CookResult(section, "ok", rows)

    result = cook.sync(to_install, to_upgrade)
    if result.message:
        (logger.error if result.status == "hard_fail" else logger.info)(result.message)
    if result.delayed_message:
        logger.info(result.delayed_message)

    installed_after = cook.list_installed()
    rows = []
    for name in cook.list_reportable(requested, installed_after):
        before = installed_before.get(name)
        after = installed_after.get(name)
        if before is None and after is not None:
            action, changed = "installed", True
        elif before is not None and after is not None and before != after:
            action, changed = "upgraded", True
        elif after is None:
            action = "failed" if result.status == "hard_fail" else "missing"
            changed = False
        else:
            action, changed = "unchanged", False
        rows.append(
            ReportRow(
                name,
                before or "(none)",
                after or before or "(none)",
                format_version(latest.get(name)),
                action,
                changed,
            )
        )

    status = result.status
    if status == "ok" and post_hook and any(row.changed for row in rows):
        if run_post_hook(post_hook) == "soft_fail":
            status = "soft_fail"
    return CookResult(section, status, rows, result.message, delayed_messages=[result.delayed_message] if result.delayed_message else [])


def apply_state_resource(cook: StateCook, name: str, current_label: str, desired_label: str, applied_label: str) -> tuple[ReportRow, Status, str]:
    """Apply one state-cook resource and build its row plus any delayed operator follow-up: pre_hook gates, apply mutates, post_hook fires on a real change; a pre_hook-gated skip reports as `ok`."""
    pre_hook, post_hook = cook.get_hooks(name)
    if pre_hook and not run_pre_hook(pre_hook):
        return ReportRow(name, current_label, current_label, desired_label, "skipped", False), "ok", ""

    outcome = cook.apply_resource(name)
    if outcome.message:
        (logger.error if outcome.status == "hard_fail" else logger.info)(outcome.message)
    if outcome.delayed_message:
        logger.info(outcome.delayed_message)
    status: Status = outcome.status
    if outcome.status == "ok" and outcome.changed and post_hook and run_post_hook(post_hook) == "soft_fail":
        status = "soft_fail"

    if status == "hard_fail":
        action, post_label = "failed", current_label  # didn't move
    elif status == "soft_fail":
        action, post_label = "post-failed", applied_label  # apply landed; the hook failed
    elif outcome.changed:
        action, post_label = "applied", applied_label
    else:
        action, post_label = "unchanged", current_label
    return ReportRow(name, current_label, post_label, desired_label, action, outcome.changed, status), status, outcome.delayed_message


def run_state(cook: StateCook, section: str, dry_run: bool) -> CookResult:
    resources = cook.list_resources()
    current = cook.get_current_state()
    desired = cook.get_desired_state()
    to_apply = [n for n in resources if current.get(n) != desired.get(n)]

    def labels(name: str) -> tuple[str, str, str]:
        """Pre-state, target and post-apply labels: a digest reads 'matches'/'differs' against the rendered recipe content, the target column shows its short content id, raw tokens pass through."""
        current_token, desired_token = current.get(name, "?"), desired.get(name, "?")
        if CONTENT_DIGEST.fullmatch(current_token):
            current_label = "matches" if current_token == desired_token else "differs"
        else:
            current_label = current_token
        applied_label = "matches" if CONTENT_DIGEST.fullmatch(desired_token) else desired_token
        return current_label, format_state(desired_token), applied_label

    def row_for(name: str) -> tuple[ReportRow, Status, str]:
        """The (row, status, delayed follow-up) one resource contributes: a dry-run preview, an unchanged-on-up row, or a real apply."""
        current_label, desired_label, applied_label = labels(name)
        will = name in to_apply

        if dry_run:
            action = "would apply" if will else "ok"
            return ReportRow(name, current_label, current_label, desired_label, action, will), "ok", ""

        if will:
            return apply_state_resource(cook, name, current_label, desired_label, applied_label)

        return ReportRow(name, current_label, current_label, desired_label, "unchanged", False), "ok", ""

    rows: list[ReportRow] = []
    statuses: list[Status] = []
    delayed_messages: list[str] = []
    for name in resources:
        row, status, delayed = row_for(name)
        rows.append(row)
        statuses.append(status)
        if delayed:
            delayed_messages.append(delayed)

    return CookResult(section, pick_worst_status(statuses), rows, delayed_messages=delayed_messages)


def run_cook(node: Node, config: dict, dry_run: bool) -> CookResult:
    cook = build_cook(node, config)
    if isinstance(cook, VersionedCook):
        return run_versioned(cook, node.id, dry_run)
    if isinstance(cook, StateCook):
        return run_state(cook, node.id, dry_run)
    return CookResult(node.id, "hard_fail", [], f"{node.id}: unknown cook kind")


def run_cook_guarded(
    node: Node,
    config: dict,
    dry_run: bool,
    dependents: tuple[str, ...] = (),
    reach: dict[str, int] | None = None,
    weights: dict[str, int] | None = None,
) -> CookResult:
    """Run one cook in its forked child and log its start line (completion is logged parent-side by log_completion); a dry-run drops the `as <user>` identity."""
    reach = reach or {}
    weights = weights or {}
    combined = reach.get(node.id, 0) - weights.get(node.id, 0)
    with cook_context(node.id):
        started = "started" if dry_run else f"started as {pwd.getpwuid(os.geteuid()).pw_name}"
        if not node.needs_root and node.depends_on:
            started += f"; depends_on {', '.join(node.depends_on)}"
        started += format_queueing(dependents, reach, combined)
        logger.info(started)
        try:
            return run_cook(node, config, dry_run)
        except Exception:
            return CookResult(node.id, "hard_fail", [], traceback.format_exc())


def fork_cook(
    node: Node,
    config: dict,
    dry_run: bool,
    dependents: dict[str, tuple[str, ...]],
    reach: dict[str, int],
    weights: dict[str, int],
) -> tuple[int, int]:
    """Fork a child to run one cook (user node drops privilege, root keeps it) and pickle its CookResult back over a pipe; main-thread-only for loguru's locks."""
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            if not node.needs_root:
                become_user()
            result = run_cook_guarded(node, config, dry_run, dependents.get(node.id, ()), reach, weights)
        except Exception:
            result = CookResult(node.id, "hard_fail", [], traceback.format_exc())
        with os.fdopen(write_fd, "wb") as out:
            out.write(pickle.dumps(result))
        os._exit(0)
    os.close(write_fd)
    return pid, read_fd


def read_child_result(read_fd: int, exit_status: int, node_id: str) -> CookResult:
    with os.fdopen(read_fd, "rb") as src:
        payload = src.read()
    if not payload:
        return CookResult(
            node_id,
            "hard_fail",
            [],
            f"{node_id} produced no result (status {exit_status}).",
        )
    try:
        return pickle.loads(payload)
    except Exception as exc:
        return CookResult(node_id, "hard_fail", [], f"{node_id} result unreadable: {exc}")


def build_dependents(graph: dict[str, set[str]]) -> dict[str, tuple[str, ...]]:
    """Reverse the dependency graph: map each node to the sorted ids that depend on it."""
    dependents: dict[str, list[str]] = {node_id: [] for node_id in graph}
    for node_id, deps in graph.items():
        for dep in deps:
            dependents[dep].append(node_id)
    return {node_id: tuple(sorted(ids)) for node_id, ids in dependents.items()}


def build_weights(config: dict, nodes: dict[str, Node]) -> dict[str, int]:
    """Each node's own work weight, read off its cook's unit_count."""
    return {node_id: build_cook(node, config).unit_count for node_id, node in nodes.items()}


def build_reach(dependents: dict[str, tuple[str, ...]], weights: dict[str, int]) -> dict[str, int]:
    """Weight each node by the work it gates: its own unit_count plus that of every transitively-downstream node, counting each once across all paths."""
    gated: dict[str, frozenset[str]] = {}

    def closure(node_id: str) -> frozenset[str]:
        if node_id not in gated:
            members = {node_id}
            for dependant in dependents[node_id]:
                members |= closure(dependant)
            gated[node_id] = frozenset(members)
        return gated[node_id]

    return {node_id: sum(weights[m] for m in closure(node_id)) for node_id in dependents}


def format_queueing(dependants: tuple[str, ...], reach: dict[str, int], combined: int) -> str:
    """The `queueing: …` start-line suffix: each dependant annotated with its reach, led by `combined` (their deduplicated total); counts of 1 are omitted."""
    if not dependants:
        return ""
    parts = [f"{dep} ({reach[dep]})" if reach.get(dep, 1) > 1 else dep for dep in dependants]
    label = f"queueing ({combined}) " if combined > 1 else "queueing"
    return f"; {label}: {', '.join(parts)}"


def format_unlocked(
    dependants: tuple[str, ...],
    satisfied: dict[str, int],
    blocker_count: dict[str, int],
) -> str:
    """The `unlocked: …` completion-line suffix: each dependant annotated `(satisfied/total)` blockers done; single-blocker dependants carry no count."""
    if not dependants:
        return ""
    parts = [f"{dep} ({satisfied[dep]}/{blocker_count[dep]})" if blocker_count[dep] > 1 else dep for dep in dependants]
    return f"; unlocked: {', '.join(parts)}"


def log_completion(
    node_id: str,
    result: CookResult,
    dependants: tuple[str, ...],
    satisfied: dict[str, int],
    blocker_count: dict[str, int],
    elapsed: float,
) -> None:
    """Emit a cook's completion line parent-side, timed from fork to reap: success unlocks dependants, failure blocks them."""
    with cook_context(node_id):
        timing = f"({format_duration(elapsed)})"
        if result.status == "ok":
            logger.info(f"completed {timing}{format_unlocked(dependants, satisfied, blocker_count)}")
        else:
            blocked = f"; blocked: {', '.join(dependants)}" if dependants else ""
            message = result.message or "see log above"
            emit = logger.warning if result.status == "soft_fail" else logger.error
            emit(f"completed with failure {timing}: {message}{blocked}")


def run_recipe_inline(config: dict, dry_run: bool) -> dict[str, CookResult]:
    """Run the DAG in this process — no fork, no privilege drop — one node at a time in topological order. The foreground/debug path (and the seam tests drive the CLI on); intra-cook concurrency (a cook's own thread pool) still applies."""
    nodes = build_nodes(config)
    graph = build_node_graph(nodes)
    dependents = build_dependents(graph)
    weights = build_weights(config, nodes)
    reach = build_reach(dependents, weights)
    blocker_count = {node_id: len(deps) for node_id, deps in graph.items()}
    satisfied: dict[str, int] = dict.fromkeys(graph, 0)
    results: dict[str, CookResult] = {}
    for node_id in TopologicalSorter(graph).static_order():
        started = time.monotonic()
        result = run_cook_guarded(nodes[node_id], config, dry_run, dependents[node_id], reach, weights)
        results[node_id] = result
        for dependant in dependents[node_id]:
            satisfied[dependant] += 1
        log_completion(node_id, result, dependents[node_id], satisfied, blocker_count, time.monotonic() - started)
        if result.status == "hard_fail":
            break
    return results


def run_recipe(config: dict, dry_run: bool) -> dict[str, CookResult]:
    """Schedule the DAG: fork ready user nodes concurrently, serialize root nodes in their own lane, reap as they finish; ties broken by reach (highest gated work first)."""
    if inline_mode():
        return run_recipe_inline(config, dry_run)
    nodes = build_nodes(config)
    graph = build_node_graph(nodes)
    dependents = build_dependents(graph)
    weights = build_weights(config, nodes)
    reach = build_reach(dependents, weights)
    blocker_count = {node_id: len(deps) for node_id, deps in graph.items()}
    satisfied: dict[str, int] = dict.fromkeys(graph, 0)
    sorter: TopologicalSorter[str] = TopologicalSorter(graph)
    sorter.prepare()
    results: dict[str, CookResult] = {}
    running: dict[int, tuple[str, int]] = {}
    started_at: dict[str, float] = {}
    pending_root: list[str] = []
    root_pid: int | None = None
    abort = False

    def settle(done_id: str, result: CookResult) -> None:
        for dependant in dependents[done_id]:
            satisfied[dependant] += 1
        elapsed = time.monotonic() - started_at.get(done_id, time.monotonic())
        log_completion(done_id, result, dependents[done_id], satisfied, blocker_count, elapsed)

    with progress_region("Cooking", total=len(nodes)) as bar:
        while sorter.is_active() and not abort:
            ready = sorted(sorter.get_ready(), key=lambda n: reach[n], reverse=True)
            for node_id in ready:
                if nodes[node_id].needs_root:
                    pending_root.append(node_id)
                else:
                    pid, read_fd = fork_cook(nodes[node_id], config, dry_run, dependents, reach, weights)
                    running[pid] = (node_id, read_fd)
                    started_at[node_id] = time.monotonic()
            if root_pid is None and pending_root:
                pending_root.sort(key=lambda n: reach[n])
                node_id = pending_root.pop()
                root_pid, read_fd = fork_cook(nodes[node_id], config, dry_run, dependents, reach, weights)
                running[root_pid] = (node_id, read_fd)
                started_at[node_id] = time.monotonic()
            if not running:
                break
            pid, exit_status = os.waitpid(-1, 0)
            node_id, read_fd = running.pop(pid)
            if pid == root_pid:
                root_pid = None
            result = read_child_result(read_fd, exit_status, node_id)
            results[node_id] = result
            settle(node_id, result)
            sorter.done(node_id)
            bar.advance()
            if result.status == "hard_fail":
                abort = True

        while running:
            pid, exit_status = os.waitpid(-1, 0)
            node_id, read_fd = running.pop(pid)
            result = read_child_result(read_fd, exit_status, node_id)
            results[node_id] = result
            settle(node_id, result)
            bar.advance()

    return results
