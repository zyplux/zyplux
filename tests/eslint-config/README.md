# eslint-config tests

Story tests exercise the public `@zyplux/eslint-config` API. Each domain contains Markdown stories, tests, and a named fixture module.

- `stories/configuration`: presets, public options, and the committed rules snapshot.
- `stories/rules`: rule behavior through ESLint's public `Linter` API, using `lint-engine.ts` and local matchers.
