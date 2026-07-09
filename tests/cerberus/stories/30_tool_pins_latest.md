# 30. [Keeping cerberus's npm tool pins at the latest release](test_30_tool_pins_latest.py)

Cerberus runs jscpd and fallow at exact versions pinned in its `tool_pins` module (`apps/cerberus/src/cerberus/tool_pins.py`), so every repo measures with the same tool — but a frozen pin rots silently. The `tool_pins_latest` bite compares each pin against npm's `dist-tags.latest` via the `registries` module. It bites only in the repo that carries the pin source, because that is the one place the fix — bump the pin, dogfood it through the gate, release cerberus — can happen; consumer repos pick the new pins up through `zyplux_deps_latest` forcing them onto the latest cerberus. There is no `--fix`: a tool version change under the gate deserves a human eye.

## 30.1 biting only where the pins are editable

### 30.1.1 skips a repo that does not carry the cerberus tool pins source

A consumer repo cannot bump a pin baked into the cerberus package, so the check skips it without a single registry lookup.

## 30.2 comparing every pin against npm's latest

### 30.2.1 passes when every pinned tool is at its latest npm release

### 30.2.2 fails naming the tool versions and pin location when a pin lags

The failure names the tool, the pinned and latest versions, the file the pin lives in, and points at bumping the pin and releasing cerberus.

### 30.2.3 errors instead of passing when the npm lookup fails

Offline or rate-limited npm must never turn into a silent pass; the lookup failure surfaces as an ERROR finding naming the tool.
