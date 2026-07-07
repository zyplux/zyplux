#!/usr/bin/python3
"""Boot-time eGPU-primary selector (egpu-prime.service, as root): when an NVIDIA eGPU is on the bus, flip boot_vga + write KWIN_DRM_DEVICES/WLR_DRM_DEVICES/AQ_DRM_DEVICES/VULKAN_ADAPTER + `prime-select nvidia`, else revert. STANDALONE: system python3 + stdlib only — a non-stdlib import breaks the graphical session at boot. Resolves /dev/dri/by-path to cardN every boot (a baked-in card number caused an earlier login loop)."""

import argparse
import os
import shutil
import subprocess
import sys
import syslog
import time
from collections.abc import Callable, Iterator
from pathlib import Path

__version__ = "1.0.0"

SYSLOG_IDENT = "egpu-prime"
NVIDIA_PCI_VENDOR_ID = "0x10de"
PCI_DEVICES_DIR = Path("/sys/bus/pci/devices")
DRI_BY_PATH_DIR = Path("/dev/dri/by-path")
EGPU_PRIMARY_CONFIG_FILE = Path("/etc/environment.d/10-egpu-primary.conf")
BOOT_VGA_OVERRIDES_DIR = Path("/run/egpu-boot-vga")
NVIDIA_DISPLAY_CLASS_PREFIXES = ("0x0300", "0x0302")


def log(message: str, level: int = syslog.LOG_INFO) -> None:
    syslog.syslog(level, message)
    print(f"{SYSLOG_IDENT}: {message}", file=sys.stderr)


def run(*command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True)


def read_pci_attr(pci_address: str, attr: str) -> str:
    try:
        return (PCI_DEVICES_DIR / pci_address / attr).read_text().strip()
    except OSError:
        return ""


def poll_until(ready: Callable[[], bool], retries: int) -> bool:
    for attempt in range(retries):
        if ready():
            return True
        if attempt < retries - 1:
            time.sleep(1)
    return False


def iter_dri_cards() -> Iterator[tuple[str, Path]]:
    for link in sorted(DRI_BY_PATH_DIR.glob("pci-*-card")):
        pci_address = link.name.removeprefix("pci-").removesuffix("-card")
        yield pci_address, link


def is_nvidia_on_pci() -> bool:
    for pci_address in PCI_DEVICES_DIR.glob("*"):
        if read_pci_attr(pci_address.name, "vendor") != NVIDIA_PCI_VENDOR_ID:
            continue
        if read_pci_attr(pci_address.name, "class").startswith(NVIDIA_DISPLAY_CLASS_PREFIXES):
            return True
    return False


def is_nvidia_drm_node_ready() -> bool:
    return any(read_pci_attr(pci_address, "vendor") == NVIDIA_PCI_VENDOR_ID and link.exists() for pci_address, link in iter_dri_cards())


def bind_boot_vga_override(boot_vga_value: str, target: Path) -> bool:
    source = BOOT_VGA_OVERRIDES_DIR / ("one" if boot_vga_value == "1" else "zero")
    mount_run = run("mount", "--bind", "-o", "ro", str(source), str(target))
    if mount_run.returncode != 0:
        log(f"boot_vga: bind {target} failed: {mount_run.stderr.strip()}", syslog.LOG_WARNING)
        return False
    return True


def flip_boot_vga() -> None:
    BOOT_VGA_OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)
    (BOOT_VGA_OVERRIDES_DIR / "one").write_text("1")
    (BOOT_VGA_OVERRIDES_DIR / "zero").write_text("0")
    for boot_vga_file in PCI_DEVICES_DIR.glob("*/boot_vga"):
        pci_address = boot_vga_file.parent.name
        is_primary = boot_vga_file.read_text().strip() == "1"
        is_nvidia = read_pci_attr(pci_address, "vendor") == NVIDIA_PCI_VENDOR_ID
        if is_nvidia and not is_primary and bind_boot_vga_override("1", boot_vga_file):
            log(f"boot_vga: {pci_address} -> 1 (eGPU primary)")
        elif not is_nvidia and is_primary and bind_boot_vga_override("0", boot_vga_file):
            log(f"boot_vga: {pci_address} -> 0 (was primary)")


def is_openable(node: str) -> bool:
    try:
        fd = os.open(node, os.O_RDWR | os.O_CLOEXEC)
    except OSError:
        return False
    os.close(fd)
    return True


def remove_env_file(reason: str) -> None:
    if EGPU_PRIMARY_CONFIG_FILE.exists():
        EGPU_PRIMARY_CONFIG_FILE.unlink()
        log(f"removed {EGPU_PRIMARY_CONFIG_FILE} ({reason})")


def write_compositor_primary() -> None:
    primary_nodes: list[str] = []
    secondary_nodes: list[str] = []
    egpu_address = ""
    for pci_address, link in iter_dri_cards():
        node = os.path.realpath(link)
        if not is_openable(node):
            remove_env_file(f"{node} not openable")
            return
        if read_pci_attr(pci_address, "vendor") == NVIDIA_PCI_VENDOR_ID:
            primary_nodes.append(node)
            egpu_address = pci_address
        else:
            secondary_nodes.append(node)
    if not primary_nodes:
        remove_env_file("no eGPU card resolved")
        return

    drm_devices = ":".join(primary_nodes + secondary_nodes)
    lines = [
        f"KWIN_DRM_DEVICES={drm_devices}",
        f"WLR_DRM_DEVICES={drm_devices}",
        f"AQ_DRM_DEVICES={drm_devices}",
    ]
    vendor_id = read_pci_attr(egpu_address, "vendor").removeprefix("0x")
    device_id = read_pci_attr(egpu_address, "device").removeprefix("0x")
    if vendor_id and device_id:
        lines.append(f"VULKAN_ADAPTER={vendor_id}:{device_id}")

    EGPU_PRIMARY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    EGPU_PRIMARY_CONFIG_FILE.write_text("\n".join(lines) + "\n")
    EGPU_PRIMARY_CONFIG_FILE.chmod(0o644)
    log(f"wrote {EGPU_PRIMARY_CONFIG_FILE}: {' | '.join(lines)}")


def query_prime() -> str:
    query_run = run("prime-select", "query")
    return query_run.stdout.strip() if query_run.returncode == 0 else "unknown"


def select_prime(prime_name: str, current: str) -> int:
    switch_run = run("prime-select", prime_name)
    if switch_run.returncode == 0:
        log(f"switched to {prime_name}")
        return 0
    error = (switch_run.stdout + switch_run.stderr).strip().replace("\n", "|")
    log(f"prime-select {prime_name} failed: {error}", syslog.LOG_WARNING)
    # `prime-select nvidia` refuses without the driver package; fall back so login still works.
    if prime_name == "nvidia" and current != "on-demand":
        log("falling back to on-demand so login still works", syslog.LOG_WARNING)
        fallback_run = run("prime-select", "on-demand")
        if fallback_run.returncode != 0:
            fallback_error = (fallback_run.stdout + fallback_run.stderr).strip().replace("\n", "|")
            log(f"fallback to on-demand also failed: {fallback_error}", syslog.LOG_WARNING)
    return 1


def parse_cli() -> None:
    parser = argparse.ArgumentParser(
        prog="egpu-prime-switch",
        description="Boot-time eGPU-primary selector: pick the NVIDIA eGPU as primary when present, else revert (run by egpu-prime.service as root).",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args()


def main() -> int:
    parse_cli()
    syslog.openlog(SYSLOG_IDENT, syslog.LOG_PID)
    nvidia_present = poll_until(is_nvidia_on_pci, retries=10)
    prime_name = "on-demand"
    if nvidia_present:
        prime_name = "nvidia"
        flip_boot_vga()
        # nvidia-drm exposes its /dev/dri node + by-path symlink seconds after the eGPU
        # appears on the bus; the env file resolves those paths, so skipping the wait loses
        # the race and KWIN_DRM_DEVICES is silently never written.
        if not poll_until(is_nvidia_drm_node_ready, retries=15):
            log("nvidia DRM node did not appear in time; recomputing compositor hint (cleared if still unresolved)", syslog.LOG_WARNING)
        write_compositor_primary()
    else:
        remove_env_file("eGPU not present")

    if shutil.which("prime-select") is None:
        log("prime-select not found; nothing to do")
        return 0

    current = query_prime()
    log(f"eGPU detected={int(nvidia_present)} current={current} desired={prime_name}")
    if current == prime_name:
        log("no change needed")
        return 0
    return select_prime(prime_name, current)


if __name__ == "__main__":
    sys.exit(main())
