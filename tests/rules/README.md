# Rule tests

Black-box tests that exercise the **published** `@zyplux/eslint-config` surface — `zyplux()` and `plugin` — exactly as a downstream project would.

## Why the split

The home of a test follows what it exercises:

- **Here — config behaviour:** does the preset wire a rule with the right options? The rule setting is read off the public `zyplux()` array and run through a one-rule `Linter`. No package internals, so the test lives outside the package.
- **In `packages/eslint-config/test` — rule implementation:** does a custom rule report and fix correctly? These use `@typescript-eslint/rule-tester`, which needs the _typed_ rule module — a package internal. They are white-box unit tests and stay beside the source.

Forcing an implementation test through the public `plugin.rules` would erase that type, and `RuleTester` cannot accept it without a banned type assertion — for zero extra coverage.
