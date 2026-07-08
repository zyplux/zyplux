# Comment

Link: <https://github.com/microsoft/vscode/issues/317948#issuecomment-4539763773>

## Patch

<https://github.com/microsoft/vscode/blob/dfbbbdf02219a79b2c324e90b14140859ea95bbb/src/vs/code/electron-main/app.ts#L240-L245>

should be

```ts
const canWarmUpScreenSources = () =>
    !isLinux && (!isMacintosh || systemPreferences.getMediaAccessStatus('screen') === 'granted');

const invalidateScreenSourceCache = () => {
    cachedScreenSources = undefined;
    if (canWarmUpScreenSources()) {
        warmUpScreenSources();
    }
};
```

`warmUpScreenSources()` is called from two spots, both currently gated by a bare `!isMacintosh` check - put `canWarmUpScreenSources()` on both. The one above (inside `invalidateScreenSourceCache`) re-fires on every new window, since `display-metrics-changed` fires when one opens. The other is a standalone call further down that runs once at boot - that's the startup popup. `isLinux` is already imported.

Happy to PR.

## Caused by

4e538f26ea3bfca625bca038af4a8d9dfc3246c8

## Rationale

An early `getSources({types:['screen']})` call was added to avoid the delay when the user later hits Issue Reporter's "Record a video of your screen."
That works silently on Windows and is guarded behind a permission check on macOS.
Wayland explicitly operates on a security model where applications cannot silently map the display space. The compositor owns the view and never hands it directly to a client.
There is no back-channel to learn what exists without showing the dialog - the consent prompt **is** the listing mechanism.

## Not `startRecording`

The renderer's `RecordingService.startRecording()` only runs on the Record click - it doesn't self-fire. The boot/every-window popup is this main-process warm-up. The `webrtc_session<n>` handshake at boot with nobody clicking is the warm-up, not `startRecording`.
