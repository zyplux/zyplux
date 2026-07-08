# Sleep crash

**2026-05-18** — Kubuntu 26.04, kernel `7.0.0-15-generic`, Tiger Lake-UY laptop
with hybrid graphics: i915 + NVIDIA 580.142-open.

## Symptom

Lock screen → hours of `s2idle` → black screen with kernel WARN:

```text
RIP: 0010:__jump_label_patch.cold+0x24/0x26
Console: switching to colour frame buffer device 240x67
```

Graphics dead, only hard reset recovers.

## Likely cause

NVIDIA out-of-tree driver + `s2idle` runtime-PM interaction. Across long
suspends the dGPU is powered down; on resume the kernel tries to flip a
static_key, reads patched bytes that don't match expectations, `bug_at()`
fires in `__jump_label_patch`. A boot-time WARN from
`arch/x86/kernel/cpu/bugs.c:3736` is already present, and split-lock
detection is set to crash on kernel-side splits — both make the system
less tolerant of any follow-on patching anomaly.

## Fixes applied (via `configure_gpu.py`)

1. Suspend switched from `s2idle` to deep S3:
   - `mem_sleep_default=deep` appended to `GRUB_CMDLINE_LINUX_DEFAULT`
   - `update-grub` rerun on change
2. NVIDIA power-management constrained — `/etc/modprobe.d/nvidia-power.conf`:
   - `NVreg_PreserveVideoMemoryAllocations=1`
   - `NVreg_DynamicPowerManagement=0x00`
   - `NVreg_EnableS0ixPowerManagement=0`
3. `nvidia-{suspend,resume,hibernate}.service` enabled.
4. `update-initramfs -u` rerun when modprobe file changes.

`linux-crashdump` added to `recipe.toml` so the next oops is captured to
`/var/crash` instead of scrolling off-screen.

## Verify after reboot

```text
cat /sys/power/mem_sleep      # expect: [deep] s2idle
cat /proc/cmdline             # includes mem_sleep_default=deep
systemctl is-enabled nvidia-suspend.service nvidia-resume.service nvidia-hibernate.service
```

## If it recurs

1. Boot kernel `7.0.0-14-generic` from GRUB → Advanced options.
   If stable, hold it:

   ```text
   sudo apt-mark hold linux-image-7.0.0-15-generic linux-modules-7.0.0-15-generic
   ```

2. Reproduce, inspect `/var/crash/` (kdump from `linux-crashdump`).
3. File on Launchpad against `linux` with `journalctl -k -b -1` excerpt.
