"""Cook execution engine: chef diffs, this acts; `run_recipe` topo-sorts the graph and forks every node (concurrent+privilege-dropped, root serialized)."""

import json
import os
import pwd
import re
import subprocess
import time
import traceback
from dataclasses import asdict, dataclass, field
from graphlib import TopologicalSorter
from typing import TYPE_CHECKING

from loguru import logger

from totchef import shell
from totchef.cook_base import CookResult, EntrySpec, ReportRow, StateCook, Status, VersionedCook
from totchef.harness import become_user
from totchef.logs import cook_context, inline_mode
from totchef.recipe_graph import (
    Node,
    build_cook,
    build_node_graph,
    build_nodes,
)
from totchef.terminal import progress_region

if TYPE_CHECKING:
    from totchef.recipe_types import RecipeConfig

STATUS_RANK: dict[Status, int] = {"ok": 0, "soft_fail": 1, "hard_fail": 2}


def pick_worst_status(statuses: list[Status]) -> Status:
    if not statuses:
        return "ok"
    return max(statuses, key=lambda s: STATUS_RANK[s])


def format_version(version: str | None) -> str:
    return version or "—"


CONTENT_DIGEST = re.compile(r"[0-9a-f]{64}")


def format_state(token: str) -> str:
    """Render a diff token for the report: a sha256 digest as its short content id (#1a2b3c4d), else as-is."""
    return f"#{token[:8]}" if CONTENT_DIGEST.fullmatch(token) else token


_SECONDS_PER_MINUTE = 60
_MINUTES_PER_HOUR = 60
_HOURS_PER_DAY = 24
_MIN_REPORTABLE_DURATION = 1e-4


def format_duration(seconds: float) -> str:
    """A wall-clock duration, stepping up per boundary: fractional seconds under a minute, then minutes+seconds, hours+minutes, days+hours."""
    if seconds < _SECONDS_PER_MINUTE:
        return f"{seconds:.4g}s" if seconds >= _MIN_REPORTABLE_DURATION else "0s"
    minutes, sec = int(seconds // _SECONDS_PER_MINUTE), int(seconds % _SECONDS_PER_MINUTE)
    if minutes < _MINUTES_PER_HOUR:
        return f"{minutes}m {sec}s"
    hours, minutes = minutes // _MINUTES_PER_HOUR, minutes % _MINUTES_PER_HOUR
    if hours < _HOURS_PER_DAY:
        return f"{hours}h {minutes}m"
    days, hours = hours // _HOURS_PER_DAY, hours % _HOURS_PER_DAY
    return f"{days}d {hours}h"


def run_pre_hook(snippet: str) -> bool:
    """A `pre_hook` guard: zero exit proceeds, non-zero skips this item (a benign skip, e.g. "browser is running", not a failure)."""
    try:
        shell.stream(["bash", "-c", snippet], note=f"pre_hook: {snippet}")
    except subprocess.CalledProcessError, OSError:
        logger.info("pre_hook not satisfied; skipping")
        return False
    else:
        return True


def run_post_hook(snippet: str) -> Status:
    """A `post_hook` runs after a successful change; non-zero -> soft failure."""
    try:
        shell.stream(["bash", "-c", snippet], note=f"post_hook: {snippet}")
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("post_hook failed: {exc}", exc=exc)
        return "soft_fail"
    else:
        return "ok"


def _plan_row(name: str, installed_before: dict[str, str], latest: dict[str, str | None]) -> ReportRow:
    """One dry-run preview row: what `run_versioned` would do for `name` without touching the system."""
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
    return ReportRow(name, installed or "(none)", installed or "(none)", format_version(available), action, changed)


def _gated_row(name: str, installed_before: dict[str, str], latest: dict[str, str | None], pending: set[str]) -> ReportRow:
    """A row for a sync the section-level `pre_hook` blocked: `name` stays put, labeled `skipped` if it was due to move, else `unchanged`."""
    installed = installed_before.get(name)
    action = "skipped" if name in pending else "unchanged"
    return ReportRow(name, installed or "(none)", installed or "(none)", format_version(latest.get(name)), action, changed=False)


def _synced_row(name: str, before: str | None, after: str | None, available: str | None, *, hard_failed: bool) -> ReportRow:
    """One post-sync report row: how `name` moved (or didn't) from its pre-sync to post-sync installed version."""
    if before is None and after is not None:
        action, changed = "installed", True
    elif before is not None and after is not None and before != after:
        action, changed = "upgraded", True
    elif after is None:
        action, changed = ("failed" if hard_failed else "missing"), False
    else:
        action, changed = "unchanged", False
    return ReportRow(name, before or "(none)", after or before or "(none)", format_version(available), action, changed)


def run_versioned(cook: VersionedCook, section: str, *, dry_run: bool) -> CookResult:
    requested = cook.list_requested()
    installed_before = cook.list_installed()
    latest = cook.find_latest(requested)

    if dry_run:
        rows = [_plan_row(name, installed_before, latest) for name in requested]
        return CookResult(section, "ok", rows)

    to_install = [n for n in requested if n not in installed_before]
    to_upgrade = [n for n in requested if n in installed_before and (latest.get(n) is None or latest[n] != installed_before[n])]
    pending = set(to_install) | set(to_upgrade)
    pre_hook, post_hook = cook.get_hooks()

    if pending and pre_hook and not run_pre_hook(pre_hook):
        rows = [_gated_row(name, installed_before, latest, pending) for name in requested]
        return CookResult(section, "ok", rows)

    result = cook.sync(to_install, to_upgrade)
    if result.message:
        (logger.error if result.status == "hard_fail" else logger.info)(result.message)
    if result.delayed_message:
        logger.info(result.delayed_message)

    installed_after = cook.list_installed()
    rows = [
        _synced_row(name, installed_before.get(name), installed_after.get(name), latest.get(name), hard_failed=result.status == "hard_fail")
        for name in cook.list_reportable(requested, installed_after)
    ]

    status = result.status
    if status == "ok" and post_hook and any(row.changed for row in rows) and run_post_hook(post_hook) == "soft_fail":
        status = "soft_fail"
    return CookResult(section, status, rows, result.message, delayed_messages=[result.delayed_message] if result.delayed_message else [])


def apply_state_resource(cook: StateCook[EntrySpec], name: str, current_label: str, desired_label: str, applied_label: str) -> tuple[ReportRow, Status, str]:
    """Apply one state-cook resource and build its row plus follow-up: pre_hook gates, apply mutates, post_hook fires on change; a gated skip is `ok`."""
    pre_hook, post_hook = cook.get_hooks(name)
    if pre_hook and not run_pre_hook(pre_hook):
        return ReportRow(name, current_label, current_label, desired_label, "skipped", changed=False), "ok", ""

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


def run_state(cook: StateCook[EntrySpec], section: str, *, dry_run: bool) -> CookResult:
    resources = cook.list_resources()
    current = cook.get_current_state()
    desired = cook.get_desired_state()
    to_apply = [n for n in resources if current.get(n) != desired.get(n)]

    def labels(name: str) -> tuple[str, str, str]:
        """Pre-state, target and post-apply labels: a digest reads matches/differs against the desired content; the target column shows its short content id."""
        current_token, desired_token = current.get(name, "?"), desired.get(name, "?")
        current_label = ("matches" if current_token == desired_token else "differs") if CONTENT_DIGEST.fullmatch(current_token) else current_token
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

        return ReportRow(name, current_label, current_label, desired_label, "unchanged", changed=False), "ok", ""

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


def run_cook(node: Node, config: RecipeConfig, *, dry_run: bool) -> CookResult:
    cook = build_cook(node, config)
    if isinstance(cook, VersionedCook):
        return run_versioned(cook, node.id, dry_run=dry_run)
    if isinstance(cook, StateCook):
        return run_state(cook, node.id, dry_run=dry_run)
    return CookResult(node.id, "hard_fail", [], f"{node.id}: unknown cook kind")


@dataclass(frozen=True)
class Scheduling:
    """Per-run scheduling data off the DAG: `dependents` feeds queueing/unlocked log lines, `reach`/`weights` drive ready-node priority and wait math."""

    dependents: dict[str, tuple[str, ...]]
    reach: dict[str, int]
    weights: dict[str, int]


@dataclass
class UnlockProgress:
    """Live blocker tally: `blocker_count` is fixed off the DAG, `satisfied` increments per completion; together they drive the `(satisfied/total)` note."""

    blocker_count: dict[str, int]
    satisfied: dict[str, int]


def run_cook_guarded(node: Node, config: RecipeConfig, *, dry_run: bool, scheduling: Scheduling) -> CookResult:
    """Run one cook in its forked child and log its start line (log_completion logs completion parent-side); a dry-run drops the `as <user>` identity."""
    dependents = scheduling.dependents.get(node.id, ())
    combined = scheduling.reach.get(node.id, 0) - scheduling.weights.get(node.id, 0)
    with cook_context(node.id):
        started = "started" if dry_run else f"started as {pwd.getpwuid(os.geteuid()).pw_name}"
        if not node.needs_root and node.depends_on:
            started += f"; depends_on {', '.join(node.depends_on)}"
        started += format_queueing(dependents, scheduling.reach, combined)
        logger.info(started)
        try:
            return run_cook(node, config, dry_run=dry_run)
        except Exception:
            logger.exception("cook raised; recording as hard_fail")
            return CookResult(node.id, "hard_fail", [], traceback.format_exc())


def _encode_result(result: CookResult) -> bytes:
    """A CookResult as JSON bytes: it's built entirely from str/bool/list/dict, so JSON round-trips it exactly, without pickle's arbitrary-object surface."""
    return json.dumps(asdict(result)).encode()


def _decode_result(payload: bytes) -> CookResult:
    data = json.loads(payload)
    return CookResult(
        cook=data["cook"],
        status=data["status"],
        rows=[ReportRow(**row) for row in data["rows"]],
        message=data["message"],
        delayed_messages=data["delayed_messages"],
    )


def fork_cook(node: Node, config: RecipeConfig, *, dry_run: bool, scheduling: Scheduling) -> tuple[int, int]:
    """Fork a child to run one cook (user drops privilege, root keeps it), JSON-encode its CookResult over a pipe; main-thread-only for loguru's locks."""
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            if not node.needs_root:
                become_user()
            result = run_cook_guarded(node, config, dry_run=dry_run, scheduling=scheduling)
        except Exception:
            logger.exception("cook {node_id} crashed before producing a result", node_id=node.id)
            result = CookResult(node.id, "hard_fail", [], traceback.format_exc())
        with os.fdopen(write_fd, "wb") as out:
            out.write(_encode_result(result))
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
        return _decode_result(payload)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return CookResult(node_id, "hard_fail", [], f"{node_id} result unreadable: {exc}")


def build_dependents(graph: dict[str, set[str]]) -> dict[str, tuple[str, ...]]:
    """Reverse the dependency graph: map each node to the sorted ids that depend on it."""
    dependents: dict[str, list[str]] = {node_id: [] for node_id in graph}
    for node_id, deps in graph.items():
        for dep in deps:
            dependents[dep].append(node_id)
    return {node_id: tuple(sorted(ids)) for node_id, ids in dependents.items()}


def build_weights(config: RecipeConfig, nodes: dict[str, Node]) -> dict[str, int]:
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


def log_completion(node_id: str, result: CookResult, dependants: tuple[str, ...], progress: UnlockProgress, elapsed: float) -> None:
    """Emit a cook's completion line parent-side, timed from fork to reap: success unlocks dependants, failure blocks them."""
    with cook_context(node_id):
        timing = f"({format_duration(elapsed)})"
        if result.status == "ok":
            logger.info("completed {timing}{unlocked}", timing=timing, unlocked=format_unlocked(dependants, progress.satisfied, progress.blocker_count))
        else:
            blocked = f"; blocked: {', '.join(dependants)}" if dependants else ""
            message = result.message or "see log above"
            emit = logger.warning if result.status == "soft_fail" else logger.error
            emit(f"completed with failure {timing}: {message}{blocked}")


def run_recipe_inline(config: RecipeConfig, *, dry_run: bool) -> dict[str, CookResult]:
    """Run the DAG in-process, no fork or privilege drop, one node at a time in topo order: the foreground/debug path the seam tests drive."""
    nodes = build_nodes(config)
    graph = build_node_graph(nodes)
    dependents = build_dependents(graph)
    weights = build_weights(config, nodes)
    reach = build_reach(dependents, weights)
    scheduling = Scheduling(dependents, reach, weights)
    progress = UnlockProgress(blocker_count={node_id: len(deps) for node_id, deps in graph.items()}, satisfied=dict.fromkeys(graph, 0))
    results: dict[str, CookResult] = {}
    for node_id in TopologicalSorter(graph).static_order():
        started = time.monotonic()
        result = run_cook_guarded(nodes[node_id], config, dry_run=dry_run, scheduling=scheduling)
        results[node_id] = result
        for dependant in dependents[node_id]:
            progress.satisfied[dependant] += 1
        log_completion(node_id, result, dependents[node_id], progress, time.monotonic() - started)
        if result.status == "hard_fail":
            break
    return results


@dataclass
class _Scheduler:
    """Fork/reap state for one `run_recipe` pass: launches ready nodes (a root node queues, serialized), reaps children, folding results into shared tallies."""

    nodes: dict[str, Node]
    config: RecipeConfig
    scheduling: Scheduling
    progress: UnlockProgress
    dry_run: bool
    sorter: TopologicalSorter[str]
    results: dict[str, CookResult] = field(default_factory=dict)
    running: dict[int, tuple[str, int]] = field(default_factory=dict)
    started_at: dict[str, float] = field(default_factory=dict)
    pending_root: list[str] = field(default_factory=list)
    root_pid: int | None = None

    def _fork(self, node_id: str) -> int:
        pid, read_fd = fork_cook(self.nodes[node_id], self.config, dry_run=self.dry_run, scheduling=self.scheduling)
        self.running[pid] = (node_id, read_fd)
        self.started_at[node_id] = time.monotonic()
        return pid

    def launch_ready(self) -> None:
        ready = sorted(self.sorter.get_ready(), key=lambda n: self.scheduling.reach[n], reverse=True)
        for node_id in ready:
            if self.nodes[node_id].needs_root:
                self.pending_root.append(node_id)
            else:
                self._fork(node_id)
        if self.root_pid is None and self.pending_root:
            self.pending_root.sort(key=lambda n: self.scheduling.reach[n])
            self.root_pid = self._fork(self.pending_root.pop())

    def reap_one(self) -> CookResult:
        pid, exit_status = os.waitpid(-1, 0)
        node_id, read_fd = self.running.pop(pid)
        if pid == self.root_pid:
            self.root_pid = None
        result = self._finish(node_id, read_fd, exit_status)
        self.sorter.done(node_id)
        return result

    def drain_one(self) -> None:
        pid, exit_status = os.waitpid(-1, 0)
        node_id, read_fd = self.running.pop(pid)
        self._finish(node_id, read_fd, exit_status)

    def _finish(self, node_id: str, read_fd: int, exit_status: int) -> CookResult:
        result = read_child_result(read_fd, exit_status, node_id)
        self.results[node_id] = result
        for dependant in self.scheduling.dependents[node_id]:
            self.progress.satisfied[dependant] += 1
        elapsed = time.monotonic() - self.started_at.get(node_id, time.monotonic())
        log_completion(node_id, result, self.scheduling.dependents[node_id], self.progress, elapsed)
        return result


def run_recipe(config: RecipeConfig, *, dry_run: bool) -> dict[str, CookResult]:
    """Schedule the DAG: fork ready nodes concurrently, serialize root nodes in their lane, reap as they finish; ties break by reach (highest work first)."""
    if inline_mode():
        return run_recipe_inline(config, dry_run=dry_run)
    nodes = build_nodes(config)
    graph = build_node_graph(nodes)
    dependents = build_dependents(graph)
    weights = build_weights(config, nodes)
    reach = build_reach(dependents, weights)
    scheduling = Scheduling(dependents, reach, weights)
    progress = UnlockProgress(blocker_count={node_id: len(deps) for node_id, deps in graph.items()}, satisfied=dict.fromkeys(graph, 0))
    sorter: TopologicalSorter[str] = TopologicalSorter(graph)
    sorter.prepare()
    scheduler = _Scheduler(nodes, config, scheduling, progress, dry_run, sorter)

    with progress_region("Cooking", total=len(nodes)) as bar:
        abort = False
        while sorter.is_active() and not abort:
            scheduler.launch_ready()
            if not scheduler.running:
                break
            result = scheduler.reap_one()
            bar.advance()
            if result.status == "hard_fail":
                abort = True

        while scheduler.running:
            scheduler.drain_one()
            bar.advance()

    return scheduler.results
