# Next

Keep this roadmap for planned work. Remove completed entries in their implementation PR.

## eslint-config

### Generate docs from tests

- for every rule-tester test pair generate markdown docs. Viewable in GitHub only for now, structure similar to typescript-eslint, unicorn, eslint-plugin-vitest etc.
- consider the best options:
  - a new command or it should execute automatically on tests or any other way (what's the common practice)
  - should regenerate everything or run smart only for changed/new rule-tests, detect renames/deletions
- rule diagnostics should link to the rule docs (ruleCreator in packages/eslint-config/src/create-rule.ts ?)
- a test to ensure no docs-tests drift

## Cerberus

### docs/roadmap/next.md

- `cerberus check --fix` to make sure this is present in every repo, at least empty - to have consistent roadmaps

## Totchef

### What's new

From the final totchef report generate a .md file stating all the new features from everything that's been upgraded and storing it to `/tmp` and posting a link to the log.
So that I could quickly review and see all the new features.
