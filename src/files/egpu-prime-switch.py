#!/usr/bin/python3
"""Boot-time eGPU-primary selector (egpu-prime.service, as root): when an NVIDIA eGPU is on the bus, flip boot_vga + write KWIN_DRM_DEVICES/VULKAN_ADAPTER + `prime-select nvidia`, else revert. STANDALONE: system python3 + stdlib only — a non-stdlib import breaks the graphical session at boot. Resolves /dev/dri/by-path to cardN every boot (a baked-in card number caused an earlier login loop)."""

import glob
import os
import shutil
import subprocess
import sys
import syslog
import time
from pathlib import Path

TAG = "egpu-prime"
NVIDIA_VENDOR = "0x10de"
PCI_DEVICES = Path("/sys/bus/pci/devices")
DRI_BY_PATH = Path("/dev/dri/by-path")
ENV_FILE = Path("/etc/environment.d/10-egpu-primary.conf")
BOOT_VGA_FAKES = Path("/run/egpu-boot-vga")
NVIDIA_DISPLAY_CLASSES = ("[0300]", "[0302]")


def log(message: str) -> None:
    syslog.syslog(message)
    print(f"{TAG}: {message}", file=sys.stderr)


def run(*command: str) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True)


def read_pci_attr(pci_address: str, attr: str) -> str:
    try:
        return (PCI_DEVICES / pci_address / attr).read_text().strip()
    except OSError:
        return ""


def nvidia_on_pci() -> bool:
    listing = run("lspci", "-nn", "-d", "10de:").stdout
    return any(cls in listing for cls in NVIDIA_DISPLAY_CLASSES)


def wait_for_nvidia(retries: int = 10) -> bool:
    for attempt in range(retries):
        if nvidia_on_pci():
            return True
        if attempt < retries - 1:
            time.sleep(1)
    return False


def nvidia_drm_node_ready() -> bool:
    for link in DRI_BY_PATH.glob("pci-*-card"):
        address = link.name.removeprefix("pci-").removesuffix("-card")
        if read_pci_attr(address, "vendor") == NVIDIA_VENDOR and link.exists():
            return True
    return False


def wait_for_nvidia_drm_node(retries: int = 15) -> bool:
    # The eGPU shows up on the PCI bus (wait_for_nvidia) seconds before nvidia-drm
    # finishes initializing and its /dev/dri node + by-path symlink appear. The
    # env file resolves those paths, so it must wait for them or it silently
    # writes nothing (lost-race → KWIN_DRM_DEVICES never applied).
    for attempt in range(retries):
        if nvidia_drm_node_ready():
            return True
        if attempt < retries - 1:
            time.sleep(1)
    return False


def bind_fake_boot_vga(value: str, target: Path) -> bool:
    fake = BOOT_VGA_FAKES / ("one" if value == "1" else "zero")
    result = run("mount", "--bind", "-o", "ro", str(fake), str(target))
    if result.returncode != 0:
        log(f"boot_vga: bind {target} failed: {result.stderr.strip()}")
        return False
    return True


def flip_boot_vga() -> None:
    BOOT_VGA_FAKES.mkdir(parents=True, exist_ok=True)
    (BOOT_VGA_FAKES / "one").write_text("1")
    (BOOT_VGA_FAKES / "zero").write_text("0")
    for boot_vga in glob.glob("/sys/bus/pci/devices/*/boot_vga"):
        flag = Path(boot_vga)
        device = flag.parent.name
        current = flag.read_text().strip()
        if read_pci_attr(device, "vendor") == NVIDIA_VENDOR:
            if current != "1" and bind_fake_boot_vga("1", flag):
                log(f"boot_vga: {device} -> 1 (eGPU primary)")
        elif current == "1" and bind_fake_boot_vga("0", flag):
            log(f"boot_vga: {device} -> 0 (was primary)")


def is_openable(node: str) -> bool:
    try:
        fd = os.open(node, os.O_RDWR | os.O_CLOEXEC)
    except OSError:
        return False
    os.close(fd)
    return True


def remove_env_file(reason: str) -> None:
    if ENV_FILE.exists():
        ENV_FILE.unlink()
        log(f"removed {ENV_FILE} ({reason})")


def write_compositor_primary() -> None:
    primary: list[str] = []
    secondary: list[str] = []
    egpu_address = ""
    for link in sorted(DRI_BY_PATH.glob("pci-*-card")):
        pci_address = link.name.removeprefix("pci-").removesuffix("-card")
        node = os.path.realpath(link)
        if not is_openable(node):
            remove_env_file(f"{node} not openable")
            return
        if read_pci_attr(pci_address, "vendor") == NVIDIA_VENDOR:
            primary.append(node)
            egpu_address = pci_address
        else:
            secondary.append(node)
    if not primary:
        remove_env_file("no eGPU card resolved")
        return

    lines = ["KWIN_DRM_DEVICES=" + ":".join(primary + secondary)]
    vendor = read_pci_attr(egpu_address, "vendor").removeprefix("0x")
    device = read_pci_attr(egpu_address, "device").removeprefix("0x")
    if vendor and device:
        lines.append(f"VULKAN_ADAPTER={vendor}:{device}")

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(lines) + "\n")
    ENV_FILE.chmod(0o644)
    log(f"wrote {ENV_FILE}: {' | '.join(lines)}")


def prime_query() -> str:
    result = run("prime-select", "query")
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def select_prime(want: str, current: str) -> int:
    result = run("prime-select", want)
    if result.returncode == 0:
        log(f"switched to {want}")
        return 0
    output = (result.stdout + result.stderr).strip().replace("\n", "|")
    log(f"prime-select {want} failed: {output}")
    # `prime-select nvidia` refuses without the driver package; fall back so
    # login still works.
    if want == "nvidia" and current != "on-demand":
        log("falling back to on-demand")
        run("prime-select", "on-demand")
    return 1


def main() -> int:
    syslog.openlog(TAG, syslog.LOG_PID)
    nvidia_present = wait_for_nvidia()
    if nvidia_present:
        want = "nvidia"
        flip_boot_vga()
        if not wait_for_nvidia_drm_node():
            log("nvidia DRM node did not appear in time; compositor hint skipped")
        write_compositor_primary()
    else:
        want = "on-demand"
        remove_env_file("eGPU not present")

    if shutil.which("prime-select") is None:
        log("prime-select not found; nothing to do")
        return 0

    current = prime_query()
    log(f"eGPU detected={int(nvidia_present)} current={current} desired={want}")
    if current == want:
        log("no change needed")
        return 0
    return select_prime(want, current)


if __name__ == "__main__":
    sys.exit(main())
