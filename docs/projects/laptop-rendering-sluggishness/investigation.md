# Laptop Rendering Sluggishness

> Note: keep this file minimalist and concise, less is more!
> Only record things we have zero doubt about to the "What We Know 100%

## Context

Kubuntu 26.04, KDE Plasma 6 (Wayland), kernel 7.0.0-15. Hybrid GPUs:

- iGPU Intel Iris Xe (`8086`, `00:02.0`) → internal panel `eDP-1` 1080p
- eGPU NVIDIA RTX 4070 (`10de:2786`, `04:00.0`, Razer Core X / TB4) → `DP-6`+`DP-7`, both 4K@60

## The Problem

GPU-accelerated client apps (VS Code, Ghostty) feel laggy **only on the 4K eGPU
monitors**; snappy on the internal 1080p panel.

## What We Know 100%

- Render-node map: `renderD128` = Intel, `renderD129` = NVIDIA.
- VS Code and Ghostty render on **Intel** (`renderD128`); KWin renders on **NVIDIA**.
- `boot_vga=1` is on Intel, `=0` on NVIDIA; `loginctl` seat master = Intel (`card1`).
- Lag tracks the **output**, not the app: same app is snappy on the 1080p Intel panel.
  KWin/Plasma and Qt-native apps (e.g. Dolphin) are snappy on the 4K screens too.
- `prime-select` is `nvidia`: KWin composites on NVIDIA, but clients still render on Intel.
- `__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia` does **not** move VS Code
  off Intel (isolated instance still held 7 handles on `renderD128`). glvnd GLX path does
  flip (`glxinfo` Intel→NVIDIA), but Chromium opens the DRM node directly via GBM.

## What We Suspect

- Root cause: clients render on Intel but display on NVIDIA 4K outputs, so KWin imports
  each 4K buffer Intel→NVIDIA over Thunderbolt every frame — the TB link is the bottleneck.
- Fix: flipping `boot_vga` to the eGPU makes it seat master → clients render on NVIDIA →
  no cross-GPU import. (Unverified until reboot.)
- `VULKAN_ADAPTER` helps move Electron specifically — low confidence; reinforcement only.

## Action Log

- 2026-05-24: Applied Option C (modeled on `all-ways-egpu`, replicated in-repo):
  - `src/files/egpu-prime-switch`: `flip_boot_vga()` bind-mounts `boot_vga` (eGPU→1,
    iGPU→0) at boot, guarded by the existing eGPU-present check. Reboot reverts.
  - `src/configure_gpu.py`: `configure_egpu_primary()` writes
    `/etc/environment.d/10-egpu-primary.conf` (`KWIN_DRM_DEVICES` eGPU-first via by-path,
    `VULKAN_ADAPTER`) only when the eGPU is detected.

## Next

- `just up`, reboot docked, then verify clients moved to `renderD129`:
  `for p in $(pgrep -f /usr/share/code/code); do ls -l /proc/$p/fd; done | grep -oE 'renderD[0-9]+' | sort | uniq -c`
- Confirm `cat /sys/bus/pci/devices/0000:04:00.0/boot_vga` = `1` and typing on a 4K screen
  is snappy.
- If VS Code still on Intel: investigate Vulkan device selection (`MESA_VK_DEVICE_SELECT`);
  `--ozone-platform=x11` only as a last resort (loses native Wayland).
