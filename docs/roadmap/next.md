# Next

## PR gate automation

- Consider exposing the [resolve-pr-gate](https://github.com/zyplux/zyp-skills/tree/main/skills/resolve-pr-gate) polling command through cz.
- Document ownership between the agent, command, review bots, and shared workflow.

## Consider publishing org_gate_base as action

- this should probably be a watcher action:
  ```yml
  uses: zyplux/.github/.github/workflows/org_gate_base.yml@main
  ```
## cerberus

- config to use `[check_name]` match checks convention (totchef-like), make sure cerberus cli uses default cerberus.toml config, but each check can be overridden with local config in the same dir where cerberus cli started

## ts testing

### cz

- should not export anything from deps-catalog.ts or release-targets.ts, use public cli interface in tests instead, cerberus should enforce that cli tool is built with optique and is only exporting commands. In fact any type of app or package should not export anything other than public interface only to be used in tests. Python doesn't export, but we still should enforce tests to not import anything from under the hood. Should be cerberus checks per app or package type.

- please review tests in the old repository <https://github.com/realSergiy/m-react-chatbot>

- all tests should use fixture pattern like m-react-chatbot: arrang, act, assert, fixtures - so that tests could read like stories, and that should be enforced by cerberus per app/package type

>Note: some ts stuff may be easier to check with eslint-config rules, maybe special rules for tests?

## eslint-config

### Generate docs from tests

- for every rule-tester test pair generate markdown docs. Viewable in GitHub only for now, structure similar to typescript-eslint, unicorn, eslint-plugin-vitest etc.
- consider the best options:
  - a new command or it should execute automatically on tests or any other way (what's the common practice)
  - should regenerate everything or run smart only for changed/new rule-tests, detect renames/deletions
- rule diagnostics should link to the rule docs (ruleCreator in packages/eslint-config/src/create-rule.ts ?)
- a test to ensure no docs-tests drift

## docs/roadmap/next.md

- `cerberus check --fix` to make sure this is present in every repo, at least empty - to have consistent roadmaps
