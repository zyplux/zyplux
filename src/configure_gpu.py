"""
Idempotent egpu-prime boot service install + GPU state probe.

Installs /usr/local/sbin/egpu-prime-switch and /etc/systemd/system/
egpu-prime.service, then enables the service. The service runs once at
boot before SDDM and selects `prime-select nvidia` when the eGPU is on
PCI, else `prime-select on-demand`. Re-runnable; only rewrites files
whose contents would change.

Also configures suspend behavior to avoid s2idle-related kernel oopses on
this Tiger Lake + NVIDIA hybrid setup (see docs/investigations/sleep-crash.md):
forces deep S3 via GRUB cmdline and pins NVIDIA power-management options.

Makes the eGPU the primary render GPU so Wayland clients render on it instead of
the iGPU (see docs/projects/laptop-rendering-sluggishness/investigation.md). Two
layers: egpu-prime-switch flips boot_vga at boot (the seat-primary lever logind +
KWin + clients follow), and this playbook writes /etc/environment.d so KWin and
Vulkan clients get the same hint.

NVIDIA driver packages live in recipe.toml; the [apt_pkg] cook runs first
(this playbook declares depends_on = ["apt_pkg"]).
"""

import re
import subprocess
from pathlib import Path

from loguru import logger
from toon_format import encode

from harness import (
    start_log_tee,
    stream_subprocess,
    write_if_changed,
)

SCRIPT = Path(__file__).resolve()
FILES_DIR = SCRIPT.parent / "files"

EGPU_SWITCH_SRC = FILES_DIR / "egpu-prime-switch"
EGPU_SERVICE_SRC = FILES_DIR / "egpu-prime.service"
EGPU_SWITCH_DST = Path("/usr/local/sbin/egpu-prime-switch")
EGPU_SERVICE_DST = Path("/etc/systemd/system/egpu-prime.service")

NVIDIA_MODPROBE_DST = Path("/etc/modprobe.d/nvidia-power.conf")
NVIDIA_MODPROBE_CONTENT = (
    b"options nvidia NVreg_PreserveVideoMemoryAllocations=1\n"
    b"options nvidia NVreg_DynamicPowerManagement=0x00\n"
    b"options nvidia NVreg_EnableS0ixPowerManagement=0\n"
)
NVIDIA_SLEEP_SERVICES = (
    "nvidia-suspend.service",
    "nvidia-resume.service",
    "nvidia-hibernate.service",
)

GRUB_FILE = Path("/etc/default/grub")
GRUB_SLEEP_PARAM = "mem_sleep_default=deep"
GRUB_CMDLINE_RE = re.compile(
    r'^(GRUB_CMDLINE_LINUX_DEFAULT=)(["\'])(.*?)\2',
    re.MULTILINE,
)

EGPU_PRIMARY_ENV = Path("/etc/environment.d/10-egpu-primary.conf")
PCI_DEVICES = Path("/sys/bus/pci/devices")
NVIDIA_VENDOR = "0x10de"
INTEL_VENDOR = "0x8086"
DRI_BY_PATH = Path("/dev/dri/by-path")


def install_egpu_prime() -> None:
    changed = False
    changed |= write_if_changed(
        EGPU_SWITCH_DST,
        EGPU_SWITCH_SRC.read_bytes(),
        0o755,
        note="boot-time prime-select switch",
    )
    changed |= write_if_changed(
        EGPU_SERVICE_DST,
        EGPU_SERVICE_SRC.read_bytes(),
        0o644,
        note="systemd unit, Before=display-manager",
    )
    if changed:
        stream_subprocess(
            ["systemctl", "daemon-reload"], note="systemctl daemon-reload"
        )

    enabled_state = subprocess.run(
        ["systemctl", "is-enabled", "egpu-prime.service"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if enabled_state == "enabled":
        logger.info("egpu-prime.service already enabled")
    else:
        stream_subprocess(
            ["systemctl", "enable", "egpu-prime.service"],
            note="enabling egpu-prime.service",
        )
        changed = True
    if changed:
        logger.info(
            "Reboot to let egpu-prime.service pick the PRIME mode before SDDM starts."
        )


def configure_nvidia_power() -> None:
    changed = write_if_changed(
        NVIDIA_MODPROBE_DST,
        NVIDIA_MODPROBE_CONTENT,
        0o644,
        note="NVIDIA suspend / runtime-PM options",
    )
    for svc in NVIDIA_SLEEP_SERVICES:
        state = subprocess.run(
            ["systemctl", "is-enabled", svc],
            capture_output=True,
            text=True,
        ).stdout.strip()
        if state == "enabled":
            logger.info(f"{svc} already enabled")
        elif state in ("disabled", "alias", "indirect"):
            stream_subprocess(["systemctl", "enable", svc], note=f"enabling {svc}")
        else:
            logger.warning(f"{svc} skipped (state: {state or 'missing'})")
    if changed:
        stream_subprocess(["update-initramfs", "-u"], note="update-initramfs -u")


def configure_grub_sleep() -> None:
    text = GRUB_FILE.read_text()
    match = GRUB_CMDLINE_RE.search(text)
    if not match:
        logger.warning(f"GRUB_CMDLINE_LINUX_DEFAULT not found in {GRUB_FILE}; skipping")
        return
    params = match.group(3).split()
    if GRUB_SLEEP_PARAM in params:
        logger.info(f"Unchanged: {GRUB_FILE}  ({GRUB_SLEEP_PARAM} already set)")
        return
    params = [p for p in params if not p.startswith("mem_sleep_default=")]
    params.append(GRUB_SLEEP_PARAM)
    new_line = f"{match.group(1)}{match.group(2)}{' '.join(params)}{match.group(2)}"
    GRUB_FILE.write_text(text[: match.start()] + new_line + text[match.end() :])
    logger.info(f"Writing  : {GRUB_FILE}  (added {GRUB_SLEEP_PARAM})")
    stream_subprocess(["update-grub"], note="update-grub")


def find_card_by_path(vendor: str) -> Path | None:
    """The stable /dev/dri/by-path/*-card symlink for the GPU of the given PCI
    vendor, or None if absent (e.g. eGPU unplugged). by-path is keyed by PCI
    address, so it survives card0/card1 renumbering across reboots."""
    for card in sorted(DRI_BY_PATH.glob("pci-*-card")):
        address = card.name.removeprefix("pci-").removesuffix("-card")
        if read_pci_attr(address, "vendor") == vendor:
            return card
    return None


def read_pci_attr(address: str, attr: str) -> str:
    try:
        return (PCI_DEVICES / address / attr).read_text().strip()
    except OSError:
        return ""


def configure_egpu_primary() -> None:
    """Method 3 (compositor hint): point KWin (KWIN_DRM_DEVICES) and Vulkan clients
    (VULKAN_ADAPTER) at the eGPU as primary, reinforcing the boot_vga switch that
    egpu-prime-switch performs. Written only when the eGPU is connected so an
    undocked re-run leaves any existing file untouched (idle re-runs stay quiet)."""
    egpu_card = find_card_by_path(NVIDIA_VENDOR)
    igpu_card = find_card_by_path(INTEL_VENDOR)
    if egpu_card is None or igpu_card is None:
        logger.info(f"Skipped : {EGPU_PRIMARY_ENV}  (eGPU not detected; leaving as-is)")
        return

    lines = [f"KWIN_DRM_DEVICES={egpu_card}:{igpu_card}"]
    egpu_address = egpu_card.name.removeprefix("pci-").removesuffix("-card")
    vendor = read_pci_attr(egpu_address, "vendor").removeprefix("0x")
    device = read_pci_attr(egpu_address, "device").removeprefix("0x")
    if vendor and device:
        lines.append(f"VULKAN_ADAPTER={vendor}:{device}")

    write_if_changed(
        EGPU_PRIMARY_ENV,
        "\n".join(lines) + "\n",
        0o644,
        note="KWin + Vulkan eGPU-primary hint",
    )


def build_gpu_state_row() -> dict:
    def capture_stdout(*cmd: str) -> str:
        completed = subprocess.run(list(cmd), capture_output=True, text=True)
        return completed.stdout.strip() if completed.returncode == 0 else "(error)"

    nvidia_devices = capture_stdout("lspci", "-nn", "-d", "10de:")
    is_nvidia_on_pci = bool(re.search(r"\[030[02]\]", nvidia_devices))
    prime_mode = capture_stdout("prime-select", "query") or "(not installed)"
    return {
        "nvidia_on_pci": "yes" if is_nvidia_on_pci else "no",
        "prime_mode": prime_mode,
    }


def main() -> None:
    start_log_tee()

    install_egpu_prime()
    configure_nvidia_power()
    configure_grub_sleep()
    configure_egpu_primary()

    logger.info("Current GPU state:")
    for line in encode([build_gpu_state_row()]).splitlines():
        logger.info(line)

    logger.info("Done.")


if __name__ == "__main__":
    main()
