# Roadmap for eslint-config

## Generate docs from tests
- for every rule-tester test pair generate markdown docs. Viewable in GitHub only for now, structure similar to typescript-eslint, unicorn, eslint-plugin-vitest etc.
- consider the best options:
  - a new command or it should execute automatically on tests or any other way (what's the common practice)
  - should regenerate everything or run smart only for changed/new rule-tests, detect renames/deletions
- rule diagnostics should link to the rule docs (ruleCreator in packages/eslint-config/src/create-rule.ts ?)
- a test to ensure no docs-tests drift
