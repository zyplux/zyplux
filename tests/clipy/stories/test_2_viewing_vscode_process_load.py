"""Story: ctop labels every VS Code process tree member by role or owning extension, colored by cpu load."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast, override

import psutil
from clipy import ctop
from clipy.ctop import (
    ProcessRow,
    attribute_profile,
    build_view,
    describe_script,
    get_cpu_style,
    get_role_style,
    get_row_style,
    label_role,
)
from rich.console import Console

if TYPE_CHECKING:
    import pytest
    from typer.testing import CliRunner


def render(view: object) -> str:
    console = Console(record=True, width=100, color_system=None)
    console.print(view)
    return console.export_text()


@dataclass
class FakeProcess:
    """A duck-typed stand-in for psutil.Process, covering only the members sample_processes touches."""

    pid: int
    process_name: str
    ppid: int = 0
    cmdline_args: list[str] = field(default_factory=list)
    cpu_percent_value: float = 0.0
    rss_bytes: int = 0
    subtree: list[FakeProcess] = field(default_factory=list)

    @property
    def info(self) -> dict[str, object]:
        return {"name": self.process_name, "ppid": self.ppid}

    def name(self) -> str:
        return self.process_name

    def cmdline(self) -> list[str]:
        return self.cmdline_args or [self.process_name]

    def cpu_percent(self) -> float:
        return self.cpu_percent_value

    def memory_info(self) -> object:
        return type("MemInfo", (), {"rss": self.rss_bytes})()

    def children(self, *, recursive: bool = True) -> list[FakeProcess]:
        if not recursive:
            return list(self.subtree)
        descendants: list[FakeProcess] = []
        for child in self.subtree:
            descendants.append(child)
            descendants.extend(child.children(recursive=True))
        return descendants

    @staticmethod
    def oneshot() -> object:
        return nullcontext()


# 2.1 labeling a process by its role or owning extension


def test_2_1_1_chromium_process_types_map_to_friendly_role_names() -> None:
    assert label_role(["code", "--type=renderer"], "code", is_main=False) == "window"
    assert label_role(["code", "--type=gpu-process"], "code", is_main=False) == "gpu"


def test_2_1_2_an_extension_host_is_distinguished_from_a_plain_node_service() -> None:
    cmdline = ["code", "--type=utility", "--utility-sub-type=node.mojom.NodeService", "--inspect-port=1234"]
    assert label_role(cmdline, "code", is_main=False) == "extension host"
    plain = ["code", "--type=utility", "--utility-sub-type=node.mojom.NodeService"]
    assert label_role(plain, "code", is_main=False) == "node service"


def test_2_1_3_network_service_processes_are_labeled() -> None:
    cmdline = ["code", "--type=utility", "--utility-sub-type=network.mojom.NetworkService"]
    assert label_role(cmdline, "code", is_main=False) == "network service"


def test_2_1_4_an_unrecognized_chromium_type_is_shown_as_is() -> None:
    assert label_role(["code", "--type=utility"], "code", is_main=False) == "utility"


def test_2_1_5_the_main_process_of_a_variant_is_labeled_main() -> None:
    assert label_role(["code-insiders"], "code-insiders", is_main=True) == "main"


def test_2_1_6_a_user_installed_extension_process_is_labeled_by_its_extension_id() -> None:
    cmdline = ["node", "/home/user/.vscode-insiders/extensions/foo.bar-1.2.3/dist/extension.js"]
    assert label_role(cmdline, "node", is_main=False) == "ext:foo.bar"


def test_2_1_7_a_builtin_extension_process_is_labeled_distinctly_from_a_user_installed_one() -> None:
    cmdline = ["node", "/opt/code/resources/app/extensions/git-9.9.9/dist/main.js"]
    assert label_role(cmdline, "node", is_main=False) == "builtin:git"


def test_2_1_8_a_vs_code_helper_process_with_no_extension_dir_falls_back_to_its_script_path() -> None:
    cmdline = ["code", "/opt/code/resources/app/out/bootstrap-fork.js"]
    assert label_role(cmdline, "code", is_main=False) == "out/bootstrap-fork.js"
    assert describe_script(cmdline, "code") == "out/bootstrap-fork.js"


def test_2_1_9_an_unrelated_process_keeps_its_own_process_name() -> None:
    assert label_role(["zsh"], "zsh", is_main=False) == "zsh"


def test_2_1_10_a_process_with_no_path_like_argument_falls_back_to_its_name() -> None:
    assert describe_script(["proc", "-x", "--flag"], "proc") == "proc"


# 2.2 coloring rows and cells by cpu load


def test_2_2_1_cpu_percent_maps_to_a_busy_yellow_or_idle_color_tier() -> None:
    assert get_cpu_style(60.0) == "bold red"
    assert get_cpu_style(25.0) == "yellow"
    assert get_cpu_style(10.0) == "green"
    assert get_cpu_style(0.1) == "dim"


def test_2_2_2_extension_and_builtin_roles_get_distinct_colors() -> None:
    assert get_role_style("ext:foo.bar") == "cyan"
    assert get_role_style("builtin:git") == "bright_blue"
    assert get_role_style("extension host") == "magenta"
    assert not get_role_style("window")


def test_2_2_3_a_busy_row_is_highlighted_an_idle_row_is_dimmed() -> None:
    assert get_row_style(51.0) == "bold red"
    assert not get_row_style(10.0)
    assert get_row_style(0.1) == "dim"


# 2.3 attributing an extension host's cpu to the owning extension


def test_2_3_1_profiler_hit_counts_are_attributed_and_expressed_as_a_percentage_share() -> None:
    profile = {
        "nodes": [
            {"callFrame": {"url": "file:///home/u/.vscode/extensions/foo.bar-1.2.3/x.js"}, "hitCount": 10},
            {"callFrame": {"url": "file:///opt/code/resources/app/extensions/git-9.9.9/x.js"}, "hitCount": 5},
            {"callFrame": {"url": "file:///opt/code/resources/app/out/vs/x.js"}, "hitCount": 3},
            {"callFrame": {"url": ""}, "hitCount": 2},
        ]
    }

    assert attribute_profile(profile) == [
        ("ext:foo.bar", 50.0),
        ("builtin:git", 25.0),
        ("vscode-core", 15.0),
        ("native/gc", 10.0),
    ]


# 2.4 rendering the live view


def test_2_4_1_an_empty_process_list_shows_a_friendly_empty_state() -> None:
    assert "no VS Code processes found" in render(build_view([], visible_count=None))


def test_2_4_2_populated_rows_show_pid_role_and_attributed_sub_rows() -> None:
    rows = [
        ProcessRow(pid=111, variant="insiders", role="extension host", cpu_percent=42.0, rss_bytes=123_456_789),
        ProcessRow(pid=222, variant="insiders", role="window", cpu_percent=1.0, rss_bytes=50_000_000),
    ]
    attribution = {111: [("ext:foo.bar", 80.0), ("vscode-core", 20.0)]}

    text = render(build_view(rows, visible_count=None, attribution=attribution))

    assert "111" in text
    assert "extension host" in text
    assert "└ ext:foo.bar" in text
    assert "222" in text
    assert "window" in text


def test_2_4_3_the_interactive_hint_communicates_profiling_state_and_hidden_row_count() -> None:
    rows = [ProcessRow(pid=i, variant="insiders", role="window", cpu_percent=1.0, rss_bytes=1) for i in range(3)]

    off = render(build_view(rows, visible_count=1, attribution=None, profiling=False, interactive=True))
    pending = render(build_view(rows, visible_count=None, attribution=None, profiling=True, interactive=True))
    on = render(build_view(rows, visible_count=None, attribution={}, profiling=True, interactive=True))

    assert "profiling off" in off
    assert "2 quieter" in off
    assert "profiling…" in pending
    assert "profiling on" in on


# 2.5 sampling the real process tree (against a faked psutil)


def test_2_5_1_finds_main_processes_by_excluding_ones_whose_own_parent_is_also_vscode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shell = FakeProcess(pid=1, process_name="bash")
    main = FakeProcess(pid=100, process_name="code-insiders", ppid=1)
    renderer = FakeProcess(pid=101, process_name="code-insiders", ppid=100)
    registry = {1: shell, 100: main, 101: renderer}
    monkeypatch.setattr(ctop.psutil, "process_iter", lambda _attrs: iter([shell, main, renderer]))
    monkeypatch.setattr(ctop.psutil, "Process", lambda pid: registry[pid])

    mains = ctop.find_main_processes()

    assert [proc.pid for proc in mains] == [100]


def test_2_5_2_a_main_process_survives_a_failed_parent_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    main = FakeProcess(pid=100, process_name="code-insiders", ppid=1)
    monkeypatch.setattr(ctop.psutil, "process_iter", lambda _attrs: iter([main]))

    def raise_no_such_process(pid: int) -> FakeProcess:
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(ctop.psutil, "Process", raise_no_such_process)

    assert [proc.pid for proc in ctop.find_main_processes()] == [100]


def test_2_5_3_sample_processes_labels_sorts_by_cpu_and_forgets_dead_pids(monkeypatch: pytest.MonkeyPatch) -> None:
    shell = FakeProcess(pid=1, process_name="bash")
    child = FakeProcess(
        pid=101,
        process_name="code-insiders",
        ppid=100,
        cmdline_args=["code-insiders", "--type=gpu-process"],
        cpu_percent_value=50.0,
        rss_bytes=200,
    )
    main = FakeProcess(
        pid=100,
        process_name="code-insiders",
        ppid=1,
        cmdline_args=["code-insiders"],
        cpu_percent_value=5.0,
        rss_bytes=100,
        subtree=[child],
    )
    registry = {1: shell, 100: main, 101: child}
    monkeypatch.setattr(ctop.psutil, "process_iter", lambda _attrs: iter([main]))
    monkeypatch.setattr(ctop.psutil, "Process", lambda pid: registry[pid])
    tracked = cast("dict[int, psutil.Process]", {999: FakeProcess(pid=999, process_name="ghost")})

    rows = ctop.sample_processes(tracked)

    assert [(row.pid, row.role) for row in rows] == [(101, "gpu"), (100, "main")]
    assert set(tracked) == {100, 101}


def test_2_5_4_a_process_that_dies_mid_sample_is_dropped_without_derailing_the_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RacyProcess(FakeProcess):
        @staticmethod
        @override
        def oneshot() -> object:
            raise psutil.NoSuchProcess(202)

    ok_child = FakeProcess(
        pid=201, process_name="code-insiders", ppid=200, cmdline_args=["code-insiders", "--type=renderer"]
    )
    dying_child = RacyProcess(pid=202, process_name="code-insiders", ppid=200)
    main = FakeProcess(pid=200, process_name="code-insiders", ppid=1, subtree=[ok_child, dying_child])
    registry = {1: FakeProcess(pid=1, process_name="bash"), 200: main}
    monkeypatch.setattr(ctop.psutil, "process_iter", lambda _attrs: iter([main, main]))
    monkeypatch.setattr(ctop.psutil, "Process", lambda pid: registry[pid])

    rows = ctop.sample_processes({})

    assert {row.pid for row in rows} == {200, 201}


def test_2_5_5_a_process_tree_that_vanishes_mid_scan_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    class VanishingProcess(FakeProcess):
        @override
        def children(self, **_kwargs: object) -> list[FakeProcess]:
            raise psutil.NoSuchProcess(self.pid)

    main = VanishingProcess(pid=300, process_name="code-insiders", ppid=1)
    registry = {1: FakeProcess(pid=1, process_name="bash")}
    monkeypatch.setattr(ctop.psutil, "process_iter", lambda _attrs: iter([main]))
    monkeypatch.setattr(ctop.psutil, "Process", lambda pid: registry[pid])

    assert ctop.sample_processes({}) == []


def test_2_5_6_only_busy_extension_hosts_are_considered_for_profiling() -> None:
    rows = [
        ProcessRow(pid=1, variant="insiders", role="window", cpu_percent=99.0, rss_bytes=1),
        ProcessRow(pid=2, variant="insiders", role="extension host", cpu_percent=0.1, rss_bytes=1),
    ]

    assert ctop.profile_busy_exthosts(rows) == {}


def test_2_5_7_visible_row_capacity_never_drops_below_the_documented_floor() -> None:
    min_visible_rows = 5
    assert ctop.get_visible_row_capacity() >= min_visible_rows


def test_2_5_8_raw_keyboard_and_read_key_are_no_ops_outside_a_real_tty() -> None:
    with ctop.raw_keyboard():
        pass

    assert ctop.read_key(0.01) is None


# 2.6 the cli


def test_2_6_1_version_flag_prints_the_version_and_exits_cleanly(cli: CliRunner) -> None:
    result = cli.invoke(ctop.app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == ctop.__version__


def test_2_6_2_a_single_snapshot_runs_end_to_end_against_the_real_machine(cli: CliRunner) -> None:
    result = cli.invoke(ctop.app, ["--once"])

    assert result.exit_code == 0
    assert "ctop" in result.output
