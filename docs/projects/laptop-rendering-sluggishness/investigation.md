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
- The first Option C attempt caused a **login loop** (greeter → black screen → greeter),
  docked *and* undocked. Root cause: `KWIN_DRM_DEVICES` is colon-separated, but we wrote the
  `/dev/dri/by-path/pci-0000:04:00.0-card` symlinks — whose names embed the colon-bearing PCI
  address. KWin split on every colon (`journalctl -b -3`: `Failed to open drm device
  /dev/dri/by-path/pci-0000` / `04` / `00.0-card` … `No suitable DRM devices have been
  found`) → compositor aborts. Static file written once while docked → poisoned every boot,
  hence undocked failed too. Card device paths (`/dev/dri/cardN`) are colon-free but renumber
  per boot; the by-path symlinks are stable but colon-bearing — there is no stable+colon-free
  name, so the list must be resolved at boot.

## What We Suspect

- Root cause: clients render on Intel but display on NVIDIA 4K outputs, so KWin imports
  each 4K buffer Intel→NVIDIA over Thunderbolt every frame — the TB link is the bottleneck.
- Fix: flipping `boot_vga` to the eGPU makes it seat master → clients render on NVIDIA →
  no cross-GPU import. (Unverified until reboot.)
- `VULKAN_ADAPTER` helps move Electron specifically — low confidence; reinforcement only.

## Action Log

- 2026-05-24: Applied Option C (boot_vga flip + `KWIN_DRM_DEVICES`/`VULKAN_ADAPTER` env
  file). Rebooted → **login loop**, recovered via TTY (disabled service, removed conf).
- 2026-05-24: Fixed and reworked. `egpu-prime-switch` is now a standalone `/usr/bin/python3`
  stdlib-only script (no repo/uv/loguru deps — it runs as root before login). At boot, when
  the eGPU is present it: flips `boot_vga`, and writes `/etc/environment.d/10-egpu-primary.conf`
  resolving each `by-path` symlink to its colon-free `/dev/dri/cardN` (eGPU first), skipping
  any node that can't open; when absent it removes the file. `configure_gpu.py` no longer
  writes the env file (static install-time file was the staleness trap). Dry-run on the docked
  system now yields `KWIN_DRM_DEVICES=/dev/dri/card0:/dev/dri/card1` (card0 = eGPU), both nodes
  present — the colon-split crash is gone. Not yet reboot-tested.

## Next

- `just up`, reboot docked. (`boot_vga` flip is still unverified in isolation — keep a TTY
  ready: `sudo systemctl disable --now egpu-prime.service && sudo rm -f /etc/environment.d/10-egpu-primary.conf`,
  then reboot, recovers it.)
- Verify clients moved off Intel:
  `for p in $(pgrep -f /usr/share/code/code); do ls -l /proc/$p/fd; done | grep -oE 'renderD[0-9]+' | sort | uniq -c`
- Confirm `cat /sys/bus/pci/devices/0000:04:00.0/boot_vga` = `1` and typing on a 4K screen
  is snappy.
- If VS Code still on Intel: investigate Vulkan device selection (`MESA_VK_DEVICE_SELECT`);
  `--ozone-platform=x11` only as a last resort (loses native Wayland).
