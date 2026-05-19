# System Performance Tweaks on eGPU Wayland Box

>Note: keep this file minimalist and concise, less is more!

## The Problem

KDE Plasma on Wayland, Tiger Lake laptop + Razer Core X Chroma (RTX 4070) over
TB4. Apps feel sluggish; YouTube playback in Brave intermittently fails to
display. Determine the cause and bring perf up. Reneder on eGPU where possible.

## What we know 100%

- Hardware: Intel Iris Xe iGPU (`00:02.0` → `/dev/dri/renderD128`) + NVIDIA RTX 4070 eGPU in Razer Core X Chroma over TB4 (`04:00.0` → `/dev/dri/renderD129`).
- `prime-select` is `nvidia`. KWin composites on the eGPU.
- Brave's GPU process renders on the **iGPU** regardless of flags: Chromium detects `Optimus: true` and silently injects `--render-node-override=/dev/dri/renderD128`. Brave-side render-node-override is a no-op.
- VS Code Insiders' Electron does **not** silently override the render node; passing `--render-node-override` hangs the GPU process at startup. Hence `[code_insiders].switches = []` in `perf.toml`.
- `nvidia-vaapi-driver` (upstream `elFarto/nvidia-vaapi-driver`, packaged in Ubuntu universe) is Firefox-targeted; under Chromium-on-TB4 it produced cross-GPU dmabuf import failures. Removed in Round 1 — iHD is the working VA-API driver here.
- Intel `iHD` is the libva auto-pick when `LIBVA_DRIVER_NAME` is unset; advertises VP9 0–3, H.264 all, HEVC Main/Main10/Main12, VP8 — covers every YouTube codec except AV1. On Chromium's trusted allowlist.
- `VaapiOnNvidiaGPUs` is required even with iHD: Chromium disables VA-API on any system where NVIDIA hardware is detected in PCI, regardless of which VA-API driver is actually loaded.
- `WaylandLinuxDrmSyncobj` is a no-op on Intel — Chromium's `rely_on_implicit_sync_for_swap_buffers` workaround overrides it. Only matters for clients rendering on NVIDIA.
- Round 1 result, measured in `about-gpu-2026-05-19T03-17-56-920Z.txt`: `eglCreateImage failed`, `vaEndPicture failed`, `ProduceSkiaGanesh failed` all dropped from 200/9/200 (in-progress) → **0**. GPU init time 2587 ms → 139 ms.
- `Runtime D3 status: Not supported` on this eGPU (`/proc/driver/nvidia/gpus/*/power`) — TB4 PCIe bridge has no RTD3 ACPI methods, so `NVreg_DynamicPowerManagement` is a no-op regardless of value.

## What we suspect

- Brave on iGPU + KWin on eGPU forces one TB4 crossing per composited frame. Forcing all clients onto the eGPU (DRI_PRIME / udev hide of renderD128 / blacklist i915) would collapse this to one device, possibly with significant gains — but a non-trivial change.
- TGL iHD lacks AV1 decode. YouTube AV1 streams fall back to software after Round 1; VP9/H.264/HEVC stay hardware. Acceptable unless we observe AV1-specific CPU spikes.

## Action Log

### 2026-05-19 — VS Code Insiders startup hang (fix)

`--render-node-override=/dev/dri/renderD129` in `perf.toml [code_insiders].switches` made the GPU process never spawn (`coredumpctl list code-insiders` shows three SIGTRAPs that day). Removed; switches now `[]`. VS Code starts cleanly.

### 2026-05-19 — Round 1: strip the nvidia-vaapi-driver stack

- `perf.toml`: dropped `[env]` block (`LIBVA_DRIVER_NAME=nvidia`, `NVD_BACKEND=direct`); dropped `VaapiIgnoreDriverChecks` from both apps' `enable-features`.
- `apt.toml`: removed `nvidia-vaapi-driver`.
- Ran `sudo apt-get remove --purge -y nvidia-vaapi-driver && sudo apt-get autoremove -y` (manually, as the harness can't elevate from agent shells).
- Patched materialized `~/.local/share/applications/brave-browser.desktop`, `code-insiders.desktop`, and `~/.vscode-insiders/argv.json` so changes take effect on next app launch without re-running `run_apps_conf.py`.
- **Regression in transit:** initially also dropped `VaapiOnNvidiaGPUs`; this disabled VA-API entirely because Chromium's NVIDIA-detected gate fired. Restored to both apps' `enable-features`. iHD now load-bearing for hardware decode.

Net: no more cross-GPU dmabuf import failures, no more NVDEC profile rejection, no more nvidia-vaapi-driver in the dpkg tree. Verify next dump shows `Video Acceleration Information` populated with iHD profile widths (VP9 8192×8192, H.264 4096×4096).

### 2026-05-19 — Code Insiders launcher cleanup

Stale `--render-node-override=/dev/dri/renderD129` removed from the `.desktop` Exec lines that `run_apps_conf.py` had previously written. Will need to re-run `sudo ./src/run_apps_conf.py` next time to confirm idempotence — repo state already matches the materialized state, so the script should be a no-op.

### 2026-05-19 — Round 1 verified

`about-gpu-2026-05-19T03-37-33-889Z.txt`: `Video Decode` / `Video Encode` both **Hardware accelerated**. iHD profiles populated — H.264 4096×4096, VP9 profile 0/2 16384×16384, HEVC main/main10 16384×16384, VP8 4096×4096. `eglCreateImage` / `vaEndPicture` / `ProduceSkiaGanesh` error counts **0**. GPU process crash count 0. Init time 331 ms (vs. 2587 ms baseline). Brave still renders on iGPU (Chromium-on-Optimus silently injects `--render-node-override=/dev/dri/renderD128` regardless of flags). One benign EGL log line remains (`eglCreateContext: Requested version is not supported` — feature-probe fallback).

### 2026-05-19 — perf.toml symmetrization

Hoisted shared Chromium feature flags into `[chromium].features`; apps keep only their extras. Dropped `--disable-features=Vulkan,DefaultANGLEVulkan,VulkanFromANGLE` from Brave — defaults keep Vulkan Disabled and ANGLE on GL (verified `about-gpu-2026-05-19T05-19-24-240Z.txt`).

## Next

- **Force Wayland clients onto the eGPU** (project goal "render on eGPU where possible"). Candidates from lowest to highest blast radius: `DRI_PRIME=1` (or `__NV_PRIME_RENDER_OFFLOAD=1` + `__GLX_VENDOR_LIBRARY_NAME=nvidia`) injected per-app via the existing `[env]` block; udev `TAG-=uaccess` rule hiding `/dev/dri/renderD128` from clients; `i915` modprobe blacklist. Note: Chromium-on-Optimus ignores `DRI_PRIME` for the same reason it ignores `--render-node-override` (Optimus-detection logic runs first), so for Brave specifically the higher-blast-radius options are the only ones that would actually move it. Decide after checking which port the active display is wired through (iGPU panel HDMI vs. eGPU DP).
