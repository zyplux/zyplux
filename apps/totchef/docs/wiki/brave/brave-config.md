# How to configure Brave

TLDR: The practical recipe for "defaults vs overrides" is: `Local State` tells you what's overridden, `brave://flags` (scraped or via CDP) tells you what's available and what the defaults are, and `brave://version` / `/proc/<pid>/cmdline` tells you what the process is actually running with right now.

## 1. Currently-active command-line switches

Open `brave://version` in the browser. The "Command Line" row shows every switch that was actually passed to the running process (including ones the launcher script injects). To get it without the GUI:

```bash
for pid in $(pgrep -x brave); do
  grep -zvq -- '--type=' /proc/$pid/cmdline && main=$pid && break
done
tr '\0' '\n' < /proc/$main/cmdline
```

The main browser process is the only `brave` whose cmdline contains no `--type=` argument (renderers/utilities/zygotes/gpu all have one). `pgrep -o brave` (oldest) is a usually-correct shortcut but is not robust across restarts of child processes.

## 2. User-enabled experiments (the `brave://flags` overrides)

These live in the `Local State` JSON file in your profile dir:

```bash
jq '.browser.enabled_labs_experiments' ~/.config/BraveSoftware/Brave-Browser/Local\ State
```

That gives you the array of flag-name + variant-index strings the user toggled away from default. Anything not in that list is at its compiled-in default.

## 3. The full list of available flags with their defaults

There's no exported manifest. Two practical options:

- **From the running browser:** load `brave://flags`, open DevTools, and either call `chrome.send('requestExperimentalFeatures')` (handled by Chromium's `FlagsUIHandler`) or scrape the DOM — each `<flags-experiment>` element carries the internal name, description, and the currently-selected option. Easiest if you launch with `--remote-debugging-port=9222` and drive it over CDP from outside the browser.
- **From source:** the canonical list is `chrome/browser/about_flags.cc` plus Brave's additions in `browser/about_flags.cc` in the `brave-core` repo. That's where "default" is actually defined.
- **Pre-captured snapshot:** [`brave-flags-default-dump.json`](brave-flags-default-dump.json) in this directory — DOM scrape of `brave://flags` on a vanilla Brave Linux install (verified unmodified per §2). 685 entries:

  ```json
  {
    "title": "...",
    "id": "kebab-case-flag-id",
    "type": "feature" | "switch" | "choice",
    "default": "...",
    "description": "...",
    "references": ["https://..."]   // optional; present on 8 entries
  }
  ```

  `type` reflects the backing `about_flags.cc` value type and dictates how to set the flag from the CLI:

  | `type` | n | `default` values | How to set |
  |---|---|---|---|
  | `feature` | 618 | `Enabled`, `Disabled`, `Enabled*` (= has field-trial params) | `--enable-features=<CppName>` / `--disable-features=<CppName>` — `<CppName>` is the PascalCase C++ identifier, **not** `id`; resolve via `about_flags.cc` |
  | `switch`  | 36  | `Enabled`, `Disabled` | `--<id>` (presence-only; absence = default) |
  | `choice`  | 31  | option label, e.g. `Default`, `200ms` | one switch per option, defined per-flag in `about_flags.cc` |

  Via UI / `Local State` (§2) `type` is irrelevant — every flag is a dropdown.

## 4. Enterprise policy overrides (separate from flags but often confused with them)

```bash
ls /etc/brave/policies/managed/ /etc/brave/policies/recommended/ 2>/dev/null
```

And `brave://policy` shows the merged result with sources.

## 5. Persistent custom switches

There is no single mechanism that works across packagings — it depends on what the launcher actually does.

- **Official .deb (`brave.com/brave/`)**: `/usr/bin/brave-browser` is the stock Chromium wrapper. It `exec`s `$HERE/brave "$@"` and does **not** read any env var or flags file. Confirm with `grep -E 'BRAVE_BROWSER_FLAGS|flags\.conf' /usr/bin/brave-browser` — expect zero matches.
- **AUR / some community builds**: ship a patched launcher that sources `~/.config/brave-flags.conf` (one switch per line). Check `head /usr/bin/brave-browser` to confirm.
- **Flatpak**: switches go in the application override, e.g. `flatpak override --user --command=brave-browser com.brave.Browser …`.

For the .deb, the durable approach is to override the launcher you actually invoke, not the binary:

```bash
# user-level override of the system .desktop file
cp /usr/share/applications/brave-browser.desktop ~/.local/share/applications/
# then edit the Exec= line to append the switches you want
```

Switches added there survive package updates (the system file gets overwritten on upgrade; the user copy doesn't). If you launch from a terminal or a custom shortcut, just bake the switches into that command — same effect, less indirection.

## 6. Performance flags worth flipping on this machine

Context: hybrid laptop with NVIDIA eGPU, Wayland session, `prime-select nvidia` when docked (see `README.md`). The README already covers VA-API decode via `libva-nvidia-driver`. The flags below address the other GPU-acceleration paths Chromium leaves off by default on Linux/NVIDIA.

The running process already has `--ozone-platform=wayland`, so the Wayland backend is in use; what's missing is hardware video, modern GL/Vulkan, and PipeWire capture.

**Video decode (extends what README.md already enables):**

```text
--enable-features=VaapiOnNvidiaGPUs,AcceleratedVideoDecodeLinuxGL,AcceleratedVideoDecodeLinuxZeroCopyGL,VaapiIgnoreDriverChecks
```

**Video encode** — offloads WebRTC and screen-recording encode to NVENC instead of x264 on the CPU:

```text
--enable-features=AcceleratedVideoEncoder
```

**PipeWire screen capture** — required for hardware-accelerated screen share under Wayland; without it `getDisplayMedia()` either fails or falls back to a slow software path:

```text
--enable-features=WebRTCPipeWireCapturer
```

**Vulkan backend for ANGLE/Skia** — replaces the GL backend with Vulkan, which on recent NVIDIA drivers (550+) tends to be faster for compositing and 2D canvas. This one is the most likely to regress on a specific driver/site combo, so flip it last and verify at `brave://gpu`:

```text
--enable-features=Vulkan,DefaultANGLEVulkan,VulkanFromANGLE
```

**Explicit sync on Wayland** — `WaylandLinuxDrmSyncobj` (Brave 1.70+, NVIDIA 555+). Big quality-of-life win for NVIDIA-on-Wayland: removes the implicit-sync flicker and improves frame pacing. Cheap to try because the NVIDIA driver advertises the extension or it silently no-ops.

```text
--enable-features=WaylandLinuxDrmSyncobj
```

### Verifying it actually took effect

After restart, check at `brave://gpu`:

- *Graphics Feature Status* → all of Canvas / Compositing / Raster / Video Decode should read **Hardware accelerated** (not "Software only" or "unavailable").
- *Video Acceleration Information* → at least VP9 and H.264 listed with decode profiles. AV1 is the most fragile; the README's enhanced-h264ify fallback applies if it regresses.
- *Vulkan* row → "Enabled" if you flipped the Vulkan flags; "Disabled" means a flag didn't apply or the driver rejected it.

### Sequence to flip them in

Don't enable all at once — if something breaks you won't know which one. Suggested order, most-safe to least-safe:

1. The video-decode block (already in README — confirm it's on).
2. `AcceleratedVideoEncoder` + `WebRTCPipeWireCapturer` — independent of the GL/Vulkan stack, very low regression risk.
3. `WaylandLinuxDrmSyncobj` — only matters under Wayland on a Wayland-capable NVIDIA driver. Visible improvement or nothing.
4. The Vulkan trio — last, because this is the one that can break specific sites or trigger driver bugs. Revert by removing the flag; nothing persists outside `Local State`.

Each of these has a corresponding entry in `brave://flags` if you'd rather toggle from the UI than the command line — the GUI route writes to `browser.enabled_labs_experiments` in `Local State` (see §2) and is reversible from the same page.
