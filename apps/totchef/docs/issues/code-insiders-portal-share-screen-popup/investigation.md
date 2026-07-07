# Spurious Screen-Share Popup on Wayland (code-insiders 1.122)

>Note: keep this file minimalist and concise, less is more!

## The Problem

VS Code Insiders 1.122.0. KDE Plasma on Wayland.
Starting 2026-05-22, a Portal dialog ("Choose which screen to share with the requesting application") pops up unprompted whenever VS Code Insiders starts, and re-pops up whenever a window like Welcome tab, Markdown preview, an Extension's page are opened.

## What we know 100%

- Root cause is a **VS Code Insiders 1.122.0** (Electron 39.8.8) regression, confirmed by two upstream issues: `RecordingService.startRecording` (the Issue Reporter's only `getDisplayMedia` call site) fires at workbench boot and on a timer, instead of only on user capture.
  - [microsoft/vscode#317948](https://github.com/microsoft/vscode/issues/317948) — KDE, names the boot-time `startRecording`.
  - [microsoft/vscode#317955](https://github.com/microsoft/vscode/issues/317955) — GNOME, same trigger, also crashes `xdg-desktop-portal-gnome` (SIGSEGV); assigned to `deepak1556`.
- On Wayland that call routes through `xdg-desktop-portal-kde`, which paints the chooser. No app name shows because the frame carries no Flatpak/Snap app-id and an empty `parent_window`.
- Requester confirmed three ways: journal timestamp lock-step, live `busctl --user status` on the D-Bus sender (PID = running code-insiders), and the handshake in `logs/screencast.log`. The D-Bus session path uses the `webrtc_session<n>` token — emitted only by Chromium's `getDisplayMedia`.
- Triggered by any webview shown (Welcome tab, markdown preview, extension details) and re-fires on a loop.
- **Not** caused by the user's setup: a throwaway instance with fresh `--user-data-dir` and empty `--extensions-dir` still fires the full `CreateSession → SelectSources → Start` handshake (3 requests in 90 s). Rules out all extensions, profile, settings, workspace, and restored tabs.
- Onset matches the 1.121.0 → 1.122.0 bump on 2026-05-22 19:30; first popup 21:33 the same day. `argv.json`/GPU flags unchanged (last written 2026-05-19).
- `--ozone-platform=x11` does **not** suppress it (XWayland still routes through the KDE portal).
- stable `code` 1.121 doesn't have the problem.
- No fix is merged upstream yet (both issues open as of 2026-05-26); a later daily Insiders build likely resolves it, but the timeline is open-ended.

## What we suspect

- root cause determined in [`root-cause.md`](./root-cause.md)

## Action Log

### 2026-05-23 — Root cause isolated

Diagnosed via `busctl --user monitor/status`, journal correlation, and a grep sweep of VS Code core + all extensions. Confirmed framework cause with a throwaway-profile + no-extensions instance. no repo or system changes made.

### 2026-05-26 — Matched to upstream

Located issues #317948 and #317955, which pin the cause to `RecordingService.startRecording`
firing at boot. No mitigation applied yet. Root cause determined

## Next

- **Decide mitigation** (no fix applied yet): if anything we could do on and codify in `recipe.toml`, that would serve as a temporary workaround, but without downgrading to 1.121.0 nor rebuilding vscode sources: a system change, vscode setting change, etc.
