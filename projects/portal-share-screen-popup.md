# "Choose which screen to share" Popup on Wayland

>Note: keep this file minimalist and concise, less is more!

## The Problem

KDE Plasma on Wayland. Starting 2026-05-22, a Portal dialog ("Choose which
screen to share with the requesting application") pops up unprompted, names no
requester, and reappears every few minutes. Identify the requester and stop it.

## What we know 100%

- Requester is **code-insiders** (the main browser process). Confirmed three ways: journal timestamp lock-step, live `busctl --user status` on the D-Bus sender (PID = the running code-insiders), and the captured handshake in `logs/screencast.log`.
- It is a Chromium `getDisplayMedia()` call: the D-Bus session path uses the `webrtc_session<n>` token, hard-coded in Chromium's `screencast_portal.cc` and emitted only by `getDisplayMedia`. On Wayland that call must go through `xdg-desktop-portal` → `xdg-desktop-portal-kde`, which paints the chooser. No app name shows because the frame has no Flatpak/Snap app-id and passes an empty `parent_window`.
- Triggered by **any webview being shown**: startup (Welcome tab), Open Preview on any markdown file, and opening any extension's details page. It also re-fires on a ~30–60 s loop while the window is open.
- **Not** caused by anything in the user's setup. A throwaway instance with a fresh `--user-data-dir` and an empty `--extensions-dir` (zero extensions, no workspace, no settings) still fires the full `CreateSession → SelectSources → Start` handshake at startup and loops (clean-profile probe: 3 requests in 90 s). Rules out all extensions, profile, settings, workspace, and restored tabs.
- **Onset matches a runtime bump, not a config change.** `~/.vscode-insiders/argv.json` was last written 2026-05-19; the GPU flags did not change. code-insiders upgraded **1.121.0 → 1.122.0 on 2026-05-22 19:30** (`product.json` date `2026-05-22T10:00:03-07:00`, Electron 39.8.8); first popup 21:33 the same day.
- The only `getDisplayMedia` call site in all of VS Code core is the Issue Reporter's `RecordingService`; no extension references `mediaDevices`. So the spurious call originates in the **1.122 framework layer**, not app/extension JS.
- Forcing `--ozone-platform=x11` does **not** suppress it (under a Wayland login, XWayland still routes through the KDE portal). X11 is not a fix.
- `[chromium].features` reaching code-insiders are video-decode only (`VaapiOnNvidiaGPUs`, `AcceleratedVideoDecodeLinuxGL`, `AcceleratedVideoDecodeLinuxZeroCopyGL`, `WaylandLinuxDrmSyncobj`). `WebRTCPipeWireCapturer` is Brave-only and absent from code-insiders.
- apt still serves 1.121.0 builds (`apt-cache madison code-insiders` lists `1.121.0-1779185827` … `1.121.0-1778865554`); downgrade is feasible. Stable `code` is not installed.

## What we suspect

- **VS Code Insiders 1.122 regression** (Electron/Chromium bump) where webview creation and a periodic timer initiate an unwanted screen capture. Likely fixed in a later daily Insiders build.
- GPU flags not fully excluded as a contributing factor: probes still read `argv.json` (its path is not relocated by `--user-data-dir`), so a flags-stripped run was not measured. Low priority — none of the reaching flags is a capture feature.

## Action Log

### 2026-05-23 — Root cause isolated

Diagnosed via `busctl --user monitor/status`, journal correlation, and a grep
sweep of VS Code core + all extensions. Confirmed framework cause with a
controlled experiment: throwaway-profile + no-extensions instance reproduces the
popup at startup and on a ~30–60 s loop. X11 ozone tested, does not suppress.
Read-only; no repo or system changes made.

## Next

- **Decide mitigation** (no fix applied yet): (a) downgrade `apt install code-insiders=1.121.0-1779185827` + `apt-mark hold` until upstream fixes it; (b) install stable `code` and switch to it; (c) wait for a newer Insiders build and re-test. Codify whichever is chosen (version pin belongs in `recipe.toml`).
- File/locate the upstream `microsoft/vscode` issue for the 1.122 spurious-screencast regression and link it here.
