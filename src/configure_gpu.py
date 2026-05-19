#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["loguru>=0.7", "toon-format>=0.9.0b1"]
# ///
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

NVIDIA driver packages live in apt_config.toml; run configure_with_apt.py first.
"""

import re
import subprocess
from pathlib import Path

from loguru import logger
from toon_format import encode

from harness import reexec_under_sudo, run, start_log_tee, write_if_changed

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


def install_egpu_prime() -> None:
    changed = False
    changed |= write_if_changed(
        EGPU_SWITCH_DST, EGPU_SWITCH_SRC.read_bytes(),
        0o755, note="boot-time prime-select switch",
    )
    changed |= write_if_changed(
        EGPU_SERVICE_DST, EGPU_SERVICE_SRC.read_bytes(),
        0o644, note="systemd unit, Before=display-manager",
    )
    if changed:
        run("systemctl", "daemon-reload", note="systemctl daemon-reload")

    enabled_state = subprocess.run(
        ["systemctl", "is-enabled", "egpu-prime.service"],
        capture_output=True, text=True,
    ).stdout.strip()
    if enabled_state == "enabled":
        logger.info("egpu-prime.service already enabled")
    else:
        run("systemctl", "enable", "egpu-prime.service",
            note="enabling egpu-prime.service")


def configure_nvidia_power() -> None:
    changed = write_if_changed(
        NVIDIA_MODPROBE_DST, NVIDIA_MODPROBE_CONTENT, 0o644,
        note="NVIDIA suspend / runtime-PM options",
    )
    for svc in NVIDIA_SLEEP_SERVICES:
        state = subprocess.run(
            ["systemctl", "is-enabled", svc],
            capture_output=True, text=True,
        ).stdout.strip()
        if state == "enabled":
            logger.info(f"{svc} already enabled")
        elif state in ("disabled", "alias", "indirect"):
            run("systemctl", "enable", svc, note=f"enabling {svc}")
        else:
            logger.warning(f"{svc} skipped (state: {state or 'missing'})")
    if changed:
        run("update-initramfs", "-u", note="update-initramfs -u")


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
    new_line = f'{match.group(1)}{match.group(2)}{" ".join(params)}{match.group(2)}'
    GRUB_FILE.write_text(text[:match.start()] + new_line + text[match.end():])
    logger.info(f"Writing  : {GRUB_FILE}  (added {GRUB_SLEEP_PARAM})")
    run("update-grub", note="update-grub")


def build_gpu_state_row() -> dict:
    def capture_stdout(*cmd: str) -> str:
        completed = subprocess.run(list(cmd), capture_output=True, text=True)
        return completed.stdout.strip() if completed.returncode == 0 else "(error)"

    is_nvidia_on_pci = bool(capture_stdout("lspci", "-nn", "-d", "10de:"))
    prime_mode = capture_stdout("prime-select", "query") or "(not installed)"
    return {
        "nvidia_on_pci": "yes" if is_nvidia_on_pci else "no",
        "prime_mode": prime_mode,
    }


def main() -> None:
    reexec_under_sudo(SCRIPT)

    log_file = start_log_tee(SCRIPT)
    logger.info(f"Logging this run to {log_file}")

    install_egpu_prime()
    configure_nvidia_power()
    configure_grub_sleep()

    logger.info("Current GPU state:")
    print(encode([build_gpu_state_row()]))

    logger.info("Done.")
    logger.info("Reboot to let egpu-prime.service pick the PRIME mode before SDDM starts.")


if __name__ == "__main__":
    main()
