# 30. [Keeping cerberus's npm tool pins at the latest release](test_30_tool_pins_latest.py)

Cerberus runs jscpd and fallow at exact versions pinned in its `tool_pins` module (`apps/cerberus/src/cerberus/tool_pins.py`). The `tool_pins_latest` bite requires the newest stable version eligible under pnpm's one-day release quarantine, within npm's `latest` release line. It runs in the repository carrying the pin source; consumers receive updated pins through Cerberus releases.

## 30.1 biting only where the pins are editable

The bundled configuration ships this bite `off = true`, so consumer repos never even run it (see [16.6](16_cli.md)); the repo owning cerberus switches it on in its root `cerberus.toml` overlay. The pin-source detection below stays as a guard for a run that is enabled (or `--check`-named) somewhere the pins are not editable.

### 30.1.1 skips a repo that does not carry the cerberus tool pins source

A consumer repo cannot bump a pin baked into the cerberus package, so the check skips it without a single registry lookup.

## 30.2 comparing every pin against npm's latest

### 30.2.1 passes when every pinned tool is at its latest npm release

### 30.2.2 fails naming the tool versions and pin location when a pin lags

The failure names the tool, the pinned and latest versions, the file the pin lives in, and points at bumping the pin and releasing cerberus.

### 30.2.3 errors instead of passing when the npm lookup fails

Offline or rate-limited npm must never turn into a silent pass; the lookup failure surfaces as an ERROR finding naming the tool.

### 30.2.4 keeps the newest mature pin while the latest release is quarantined

### 30.2.5 requires the newest eligible pin

### 30.2.6 errors when release times are invalid or no release is eligible
