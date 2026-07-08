# eslint-config tests

Black-box tests that exercise the **published** `@zyplux/eslint-config` surface — `zyplux()`, `plugin`, and the committed `rules.json` snapshot — exactly as a downstream project would.

All tests are user stories in `stories/`: preset behaviour reads off the public `zyplux()` array or the `eslint --print-config` output, and custom-rule behaviour drives each rule through a one-rule `Linter` configured with the public `plugin` export. No package internals are imported — everything goes through `#fixtures`.
