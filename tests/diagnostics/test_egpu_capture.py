from __future__ import annotations

import importlib.util
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType


@pytest.fixture
def capture() -> ModuleType:
    path = Path(__file__).parents[2] / "docs/issues/egpu-freeze/capture.py"
    spec = importlib.util.spec_from_file_location("egpu_capture", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_attributes(directory: Path, **attributes: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in attributes.items():
        (directory / name).write_text(text)


def test_durable_logs_append_complete_timestamped_records(capture: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "capture.log"
    for text in ("first\n", "second"):
        log = capture.DurableLog(path)
        try:
            log.write(text)
        finally:
            log.close()
    lines = path.read_text().splitlines()
    assert [line.split(" ", 1)[1] for line in lines] == ["first", "second"]
    assert all(line.startswith("time_ns=") for line in lines)


def test_collect_links_reads_device_topology_and_formats_missing_counters(
    capture: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("PCI_DEVICES", "PCI_SLOTS", "THUNDERBOLT_DEVICES", "USB_DEVICES", "DRM_DEVICES"):
        directory = tmp_path / name.lower()
        directory.mkdir()
        monkeypatch.setattr(capture, name, directory)
    bridge = tmp_path / "topology/pci0000:00/0000:00:07.0"
    gpu = bridge / "0000:02:00.0"
    write_attributes(bridge, vendor="0x8086", current_link_speed="8 GT/s", current_link_width="4")
    write_attributes(
        gpu,
        vendor="0x10de",
        **{"class": "0x030000"},
        current_link_speed="16 GT/s",
        current_link_width="4",
        aer_dev_correctable="Receiver Error 3\nBad TLP 0\n",
    )
    for device in (bridge, gpu):
        (capture.PCI_DEVICES / device.name).symlink_to(device, target_is_directory=True)
    write_attributes(capture.PCI_SLOTS / "3", address="0000:02:00", adapter="1", power="1")
    write_attributes(capture.PCI_SLOTS / "4", address="0000:09:00", power="0")
    write_attributes(capture.THUNDERBOLT_DEVICES / "0-1", authorized="1", rx_speed="40.0 Gb/s")
    write_attributes(capture.USB_DEVICES / "1-2", idVendor="1532", idProduct="0f1a")
    write_attributes(capture.USB_DEVICES / "1-3", idVendor="ffff", idProduct="ffff")
    card = capture.DRM_DEVICES / "card0"
    card.mkdir()
    (card / "device").symlink_to(gpu, target_is_directory=True)
    write_attributes(capture.DRM_DEVICES / "card0-DP-1", status="connected")

    assert capture.find_egpu().name == gpu.name
    fields = capture.collect_links().split(" ")
    assert "egpu=0000:02:00.0" in fields
    assert "link[0000:02:00.0]=16_GT/s,x4" in fields
    assert "link[0000:00:07.0]=8_GT/s,x4" in fields
    assert "aer[0000:02:00.0].correctable=Receiver_Error_3|Bad_TLP_0" in fields
    assert "aer[0000:02:00.0].fatal=unavailable" in fields
    assert "slot[3].power=1" in fields
    assert not any(field.startswith("slot[4]") for field in fields)
    assert "tb[0-1].rx_speed=40.0_Gb/s" in fields
    assert "usb[chroma]=1-2" in fields
    assert "usb[ethernet]=absent" in fields
    assert "drm[card0-DP-1]=connected" in fields


def test_missing_gpu_and_debug_controls_are_safe(
    capture: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(capture, "PCI_DEVICES", tmp_path)
    assert capture.find_egpu() is None
    assert capture.collect_pci(None) == ["egpu=absent"]
    assert capture.collect_drm(None) == []
    control = tmp_path / "dynamic_debug"
    monkeypatch.setattr(capture, "DYNAMIC_DEBUG", control)
    capture.set_dynamic_debug(enabled=True)
    assert not control.exists()
    control.touch()
    capture.set_dynamic_debug(enabled=True)
    assert control.read_text() == "module thunderbolt +p\nmodule pciehp +p\n"
    capture.set_dynamic_debug(enabled=False)
    assert control.read_text() == "module thunderbolt -p\nmodule pciehp -p\n"


def test_stream_records_child_output_and_startup_errors(capture: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "stream.log"
    log = capture.DurableLog(path)
    try:
        capture.stream([sys.executable, "-c", "print('device removed')"], log, threading.Event())
        capture.stream([str(tmp_path / "missing-command")], log, threading.Event())
    finally:
        log.close()
    assert "device removed|" in path.read_text()
    assert "error=" in path.read_text()


def test_nvidia_counter_parsing_and_sysctl_arguments(capture: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **_options: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        stdout = (
            "1\n"
            if command[0] == "sysctl"
            else """
GPU 0
    Replays Since Reset : 12
    Replay Number Rollovers : 2
    Unrelated Counter : 42
"""
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout)

    monkeypatch.setattr(capture.subprocess, "run", run)
    assert capture.query_nvidia() == ["replays_since_reset=12", "replay_number_rollovers=2"]
    assert capture.get_sysctl("kernel.panic") == "1"
    capture.set_sysctl("kernel.panic", "20")
    assert commands == [
        ["nvidia-smi", "-q"],
        ["sysctl", "-n", "kernel.panic"],
        ["sysctl", "-q", "-w", "kernel.panic=20"],
    ]


@pytest.mark.parametrize("has_query_error", [False, True])
def test_sampling_records_query_completion_or_failure(
    capture: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, has_query_error: bool
) -> None:
    stop = threading.Event()

    def query() -> list[str]:
        stop.set()
        if has_query_error:
            command = ["nvidia-smi"]
            raise subprocess.CalledProcessError(1, command)
        return ["replays_since_reset=12"]

    monkeypatch.setattr(capture, "query_nvidia", query)
    path = tmp_path / "nvidia.log"
    log = capture.DurableLog(path)
    try:
        capture.sample_nvidia(log, stop)
    finally:
        log.close()
    text = path.read_text()
    assert "phase=query-start" in text
    expected = "phase=query-failed error=Command" if has_query_error else "phase=query-complete replays_since_reset=12"
    assert expected in text


def test_capture_requires_root_before_changing_system_state(
    capture: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(capture.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(sys, "argv", ["capture"])
    assert capture.main() == 1
    assert capsys.readouterr().err == "Run this script as root.\n"
