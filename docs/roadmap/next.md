# Next

## Improve resolve-pr-review-comments skill

Done:

1. Reduce verbosity and bloat, but don't drop anything important - ensure no repetition, rephrase for terse/concise language
2. Add instruction to push back hard on copilot review comments: fact-check them (online if necessary), verify if they fit the repo goals/spirit. Don't just fix blindly, take them with a grain of salt, historically I can say false positives happen on almost every PR.
3. If false positive happened and it is possible to add abstract instruction to prevent future false-positives, update copilot-instructions. But make sure it's short, concise and to the point. And it has to be abstract enough - something that can happen in future. If it cannot happen in future - don't add instruction.
4. Last step is confusing. It is supposed to verify, but it feels destructive. It should just verify without changing anything.

Todo:

5. steps that involve scripting should be codified instead in cz and called via `just <command>`
6. even the polling waiting script like this one that agent is using to wait for the copilot review
      ```bash
      OWNER=zyplux REPO=.github
      SHA=$(git rev-parse HEAD)
      echo "HEAD=$SHA"
      for _ in $(seq 1 120); do
          STATE=$(gh api "repos/$OWNER/$REPO/commits/$SHA/statuses" \
          --jq 'map(select(.context=="copilot-review-complete"))[0].state // "none"')
          echo "$(date +%T) state=$STATE"
          case "$STATE" in success|failure|error) break;; esac
          sleep 10
      done
      ```
   could be automated to either cz (maybe `just pr --watch`?) or Claude Code native /loop (if can be invoked via skill)
7. use swimlanes diagram, define ownership lanes and split for them: agent, command, copilot, workflow

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
