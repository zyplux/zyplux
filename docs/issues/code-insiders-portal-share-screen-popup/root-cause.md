# Root Cause — Spurious Screen-Share Popup (code-insiders 1.122)

## The bug in one sentence

To make the "Record screen" button in the Issue Reporter feel instant, VS Code
1.122 started **pre-loading the list of screens the moment it launches** — but on
Wayland, asking for that list *is itself* the "Choose what to share" consent
dialog. So the dialog pops up at boot, unprompted.

## What's actually happening

1. The Issue Reporter got a new "record a video of your screen" feature.
2. Enumerating monitors takes a few seconds the first time, so a developer added
   a **cache warm-up**: at startup the Electron *main* process calls
   `desktopCapturer.getSources({ types: ['screen'] })` and stashes the result, so
   that when you later click Record there's no wait.
3. On macOS this is guarded behind a permission check. On Windows and **Linux**
   it runs unconditionally, because historically "list the screens" was a silent,
   non-interactive operation on those platforms.
4. **On Wayland that assumption is false** — listing the screens isn't a silent
   query, it *is* the consent dialog. Electron's `getSources` has no choice but
   to negotiate a capture session through the desktop portal
   (`org.freedesktop.portal.ScreenCast`: `CreateSession → SelectSources →
   Start`), and the `Start` step is exactly when the compositor paints the
   "Choose what to share" chooser. So the "harmless warm-up" becomes a consent
   prompt — fired by the app itself, with no user action. The next section proves
   why this is *unavoidable* on Wayland, not just an unlucky quirk.

That's why your D-Bus trace shows the full handshake (and the `webrtc_session…`
token) at boot with nobody clicking anything.

## Why this is unavoidable on Wayland (the proof)

The warm-up assumes listing screens is a silent background call. On Wayland it
isn't, by design — and the chain below forces the popup:

1. **No client can see the screen.** Wayland isolates clients; only the
   compositor sees everything, and the protocol has no call to read or even
   enumerate the shareable screens.
2. **Capture must go through a broker.** The only path is `xdg-desktop-portal`
   (D-Bus): an app negotiates a session, the portal enforces consent, and only
   then returns a PipeWire stream. There is no list-now-consent-later mode.
3. **The dialog lives in the last of three steps.** `CreateSession` (no UI) →
   `SelectSources` (no UI) → `Start` — which the spec says *"will typically
   result [in] the portal presenting a dialog letting the user do the selection
   set up by SelectSources."* That dialog **is** the popup; the stream's PipeWire
   fd arrives only after the user picks.
4. **No query skips `Start`.** Enumerating screens and consenting to capture are
   the *same* operation — the list is produced by the chooser. The only door is
   the consent dialog.

∴ When `desktopCapturer.getSources({ types: ['screen'] })` runs on Wayland,
Chromium can only drive `CreateSession → SelectSources → Start` — so the warm-up
fires its own consent dialog at boot, with no click. That is exactly the trace:
the full handshake (with the Chromium `webrtc_session…` token) at startup. It's
not a separate bug — it's the only thing the warm-up *can* do here.

## Why the popup keeps coming back

The same warm-up is also re-run whenever the screen layout changes. The code
listens for three events:

- `display-added`
- `display-removed`
- `display-metrics-changed`

On KDE/Wayland, `display-metrics-changed` fires often (scale-factor / geometry
recalculation), and **opening any new webview or window** (Welcome tab, Markdown
preview, an extension's page) triggers that recalculation. Each event re-runs the
warm-up → a fresh portal session → another popup.

## Why the obvious explanations are wrong

- **"It's `RecordingService.startRecording` / `getDisplayMedia` in the renderer"**
  (what the two upstream issues blame first): close, but not it. That function
  only runs when *you click the Record button* — it never self-fires at boot.
  The boot-time popup comes from the **main process** cache warm-up, not the
  renderer.
- **"It names no app / GNOME's portal crashes"**: the call comes from the Electron
  main process with no window attached, so the portal has no app name or parent
  window to show. GNOME's portal additionally crashes (SIGSEGV) on that
  parentless request — a separate portal-side bug, but VS Code's unprompted call
  is what triggers it.

## How to fix

**File:** `src/vs/code/electron-main/app.ts` (around lines 231–256 in the
1.122 source; commit `4e538f26` "Issue reporter wizard" introduced it).

**Idea:** never pre-load the screen list on Linux. Only do it where listing
screens is silent (Windows, and macOS when permission is already granted). On
Linux, let it load lazily — i.e. only when the user actually clicks Record. That
lazy path already exists inside `setDisplayMediaRequestHandler` (same file,
~lines 272–287) and only runs in response to a real screen-capture request, when
showing the portal dialog is expected and wanted.

### The current (buggy) code

```ts
const warmUpScreenSources = () => {
    desktopCapturer.getSources({
        types: ['screen'],
        thumbnailSize: { width: 0, height: 0 },
    }).then(sources => { cachedScreenSources = sources; }).catch(() => { /* best-effort */ });
};
const invalidateScreenSourceCache = () => {
    cachedScreenSources = undefined;
    if (!isMacintosh || systemPreferences.getMediaAccessStatus('screen') === 'granted') {
        warmUpScreenSources();          // re-fires on every display event
    }
};
electronScreen.on('display-added', invalidateScreenSourceCache);
electronScreen.on('display-removed', invalidateScreenSourceCache);
electronScreen.on('display-metrics-changed', invalidateScreenSourceCache);
// ...
if (!isMacintosh || systemPreferences.getMediaAccessStatus('screen') === 'granted') {
    warmUpScreenSources();              // fires once at workbench boot
}
```

### The fix

Add one guard that excludes Linux, and use it in both places. `isLinux` is
already imported at the top of the file.

```ts
// desktopCapturer.getSources for screens is silent on Windows and X11, but on a
// Wayland session it goes through xdg-desktop-portal ScreenCast, which shows the
// OS "Choose what to share" consent dialog. Warming the cache there prompts the
// user unbidden at boot and on every display-metrics change, so we never warm
// eagerly on Linux — the lazy path in the request handler below covers the
// (user-initiated) record case.
const canWarmUpScreenSources = () =>
    !isLinux && (!isMacintosh || systemPreferences.getMediaAccessStatus('screen') === 'granted');

const invalidateScreenSourceCache = () => {
    cachedScreenSources = undefined;
    if (canWarmUpScreenSources()) {
        warmUpScreenSources();
    }
};
// ...
if (canWarmUpScreenSources()) {
    warmUpScreenSources();
}
```

### Why this is safe

- **No feature is lost.** When you click Record, `getDisplayMedia` runs and the
  request handler lazily lists the screens then. On Wayland the portal dialog at
  *that* moment is the intended, expected UX.
- **The only cost is on X11**, where you lose the pre-warm and the *first* Record
  click takes a couple of extra seconds. That's a fair trade for not prompting
  every user at startup — and it's absorbed by the lazy path that already exists.
- **Excluding all of Linux (not just "detected Wayland")** is deliberate: an
  XWayland app can't reliably tell at this layer whether capture will hit the
  portal, so the conservative choice avoids the bug on every Linux setup.

## TL;DR to paste on the issue

> The boot-time popup isn't `RecordingService.startRecording` (that only runs on
> the Record button click). It's the eager screen-source cache warm-up added in
> the "Issue reporter wizard" change: `app.ts` calls
> `desktopCapturer.getSources({ types: ['screen'] })` at startup (and on every
> `display-metrics-changed`) to speed up the recording feature. On Wayland that
> call goes through `xdg-desktop-portal` ScreenCast, so it *is* the consent
> dialog. Fix: don't warm up the cache on Linux — gate the warm-up with
> `!isLinux` and rely on the existing lazy enumeration inside
> `setDisplayMediaRequestHandler`, which only runs on an actual user-initiated
> capture.
