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

## Resolved

- **Fixed.** With `boot_vga` flipped to the eGPU **and** `KWIN_DRM_DEVICES` listing the eGPU
  card first, clients moved off Intel onto NVIDIA and the 4K monitors are snappy (confirmed
  by the user). The cross-GPU buffer import over Thunderbolt was the bottleneck.
- The real lever is **`KWIN_DRM_DEVICES`** (compositor-side), not any client flag. Chromium
  follows the compositor's advertised `main_device`: once KWin advertised NVIDIA as primary,
  Brave's own `--render-node-override` flipped to `renderD129` on its own. `boot_vga` alone
  did not move clients in earlier tests — the env file was the missing piece (lost to the
  colon-split crash, then to the DRM-node race, until both were fixed).
- `VULKAN_ADAPTER` rides along in the same file; no longer needs isolating.
- **Video-decode follow-on.** Moving the render node to NVIDIA broke browser HW video
  decode (4K YouTube pegged a renderer at ~130% CPU) because NVIDIA exposes no native
  VA-API driver. Fix: install `nvidia-vaapi-driver` (VA-API → NVDEC shim). No env var
  needed — with `LIBVA_DRIVER_NAME` unset, libva derives the driver name from the render
  node's kernel DRM driver (`nvidia`), so it loads `nvidia_drv_video.so` automatically.
  Confirmed: Brave `about://gpu` shows Video Decode + Encode "Hardware accelerated", 4K
  video plays with silent CPU.

## Action Log

- 2026-05-24: Applied Option C (boot_vga flip + `KWIN_DRM_DEVICES`/`VULKAN_ADAPTER` env
  file). Rebooted → **login loop**, recovered via TTY (disabled service, removed conf).
- 2026-05-24: Fixed and reworked. `egpu-prime-switch` is now a standalone `/usr/bin/python3`
  stdlib-only script (no repo/uv/loguru deps — it runs as root before login). At boot, when
  the eGPU is present it: flips `boot_vga`, and writes `/etc/environment.d/10-egpu-primary.conf`
  resolving each `by-path` symlink to its colon-free `/dev/dri/cardN` (eGPU first), skipping
  any node that can't open; when absent it removes the file. `configure_gpu.py` no longer
  writes the env file (static install-time file was the staleness trap). Also added
  `wait_for_nvidia_drm_node()` — the eGPU appears on the PCI bus seconds before nvidia-drm
  finishes and the `/dev/dri` node + by-path symlink exist, so the first reboot wrote nothing
  (lost race); the wait closes it.
- 2026-05-24: **Reboot confirmed the fix.** Journal: `boot_vga: 0000:04:00.0 -> 1`,
  `wrote …10-egpu-primary.conf: KWIN_DRM_DEVICES=/dev/dri/card0:/dev/dri/card1 | VULKAN_ADAPTER=10de:2786`,
  no KWin DRM errors, login clean. Brave `about://gpu`: `*ACTIVE*` flipped `0x8086`→`0x10de`,
  render node `renderD128`→`renderD129`, `GL_RENDERER` Intel Iris Xe→RTX 4070. VS Code fds:
  10× `renderD129` vs 1× `renderD128`. User reports the 4K monitors are now snappy. Done.
- 2026-05-24: Installed `nvidia-vaapi-driver` (via new `[snap]`/`snap_cook.py` work in the
  same `just up`) to restore HW video decode on the NVIDIA node. After reboot: Brave reports
  Video Decode + Encode "Hardware accelerated", 4K video plays with silent CPU, whole system
  feels snappy. Investigation closed.
