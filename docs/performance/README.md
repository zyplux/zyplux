# egpu-prime

Auto-select Ubuntu's `prime-select` mode at boot based on whether the
NVIDIA eGPU is connected. No manual `prime-select` toggling, no broken
login screen when the eGPU is unplugged.

## Why

On a hybrid laptop (Intel iGPU + NVIDIA dGPU/eGPU), `prime-select` controls
which GPU drives the desktop:

- `intel` — iGPU only; NVIDIA driver blacklisted. Best on battery.
- `nvidia` — NVIDIA drives everything (greeter, compositor, all apps).
  Best when an eGPU with external monitors is attached.
- `on-demand` — iGPU drives the desktop; NVIDIA is loaded but idle until
  an app is launched with `__NV_PRIME_RENDER_OFFLOAD=1` (or `prime-run`).

Setting `nvidia` is sticky and survives reboots, so unplugging the eGPU
mid-session leaves you with a session that needs a GPU that isn't there.
This service runs once at boot, before the display manager starts, and
matches the mode to current hardware.

## Files

Installable assets live in `../../files/` and are deployed by `../../perf_runner.py`.

| Source | Installs to |
|---|---|
| `../../files/egpu-prime-switch` | `/usr/local/sbin/egpu-prime-switch` |
| `../../files/egpu-prime.service` | `/etc/systemd/system/egpu-prime.service` |

## Install

```bash
sudo ../../perf_runner.py
```

Idempotent — re-run after editing `../../perf.toml`. Dry-run the boot logic
without rebooting:

```bash
sudo systemctl start egpu-prime.service
journalctl -u egpu-prime.service -b -n 30
```

Then reboot once to confirm boot-time behavior.

## How it works

1. Unit is ordered `After=bolt.service` and `Before=display-manager.service`,
   so Thunderbolt authorization has finished but SDDM/GDM hasn't started.
2. `egpu-prime-switch` polls `lspci -nn -d 10de:` for up to 10 seconds.
   Vendor ID `0x10de` = NVIDIA; class `0300`/`0302` = display controller.
3. Calls `prime-select nvidia` if found, else `prime-select on-demand`.
   No-op if already in the right mode (no `update-initramfs` churn).
4. If `prime-select nvidia` fails (driver missing, etc.), falls back to
   `on-demand` so login still works.

## Verify

After boot with the eGPU attached:

```bash
prime-select query              # -> nvidia
glxinfo -B | grep -E 'OpenGL renderer|vendor'   # -> NVIDIA GeForce RTX ...
nvidia-smi                      # 4070 visible, driver loaded
```

Without the eGPU:

```bash
prime-select query              # -> on-demand
```

## Rescue

If something gets stuck on a missing eGPU and the desktop won't start:

```
Ctrl+Alt+F3            # switch to a TTY
sudo prime-select on-demand
sudo systemctl restart display-manager
```

## Uninstall

```bash
sudo systemctl disable --now egpu-prime.service
sudo rm /etc/systemd/system/egpu-prime.service /usr/local/sbin/egpu-prime-switch
sudo systemctl daemon-reload
```

## Related: hardware video decode

`prime-select nvidia` puts rendering on the RTX, but video decode in
Chromium-based browsers also needs the VA-API → NVDEC shim. NVIDIA GPUs
don't speak VA-API natively, so without this shim Brave decodes 4K video
on the CPU even when the RTX is the active GPU.

Install (Ubuntu 26.04):

```bash
sudo apt install nvidia-vaapi-driver vainfo
```

Confirm it loads against the RTX:

```bash
LIBVA_DRIVER_NAME=nvidia vainfo
# expect VAProfileH264*, VAProfileVP9*, VAProfileHEVC*, VAProfileAV1*
```

Tell Brave to use it via environment variables in the launcher:

```
LIBVA_DRIVER_NAME=nvidia
NVD_BACKEND=direct
```

and the Brave feature flag:

```
--enable-features=VaapiOnNvidiaGPUs,AcceleratedVideoDecodeLinuxGL,AcceleratedVideoDecodeLinuxZeroCopyGL,VaapiIgnoreDriverChecks
```

Confirm at `brave://gpu` -> Video Acceleration Information that VP9 / AV1
show "Hardware accelerated" rather than "Software only".

Chromium upstream still labels NVIDIA VA-API as experimental. If AV1
regresses after a driver bump, install the `enhanced-h264ify` extension
and block AV1 to force YouTube onto VP9, which is more stable on this
shim.
