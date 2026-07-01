# Next

## Improve resolve-pr-review-comments skill

1. Reduce verbosity and bloat, but don't drop anything important - ensure no repetition, rephrase for terse/concise language
2. Add instruction to push back hard on copilot review comments: fact-check them (online if necessary), verify if they fit the repo goals/spirit. Don't just fix blindly, take them with a grain of salt, historically I can say false positives happen on almost every PR.
3. If false positive happened and it is possible to add abstract instruction to prevent future false-positives, update copilot-instructions. But make sure it's short, concise and to the point. And it has to be abstract enough - something that can happen in future. If it cannot happen in future - don't add instruction.
4. Last step is confusing. It is supposed to verify, but it feels destructive. It should just verify without changing anything.
5. steps that involve scripting should be codified instead in cz and called via just
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
  could be automated to either cz (maybe `just pr --watch`?) or Claud Code native /loop (if can be invoked via skill)

## Fix root README.md

- should describe each workspace member briefly instead

## Consider publishing org_gate_base as action

- this should probably be a watcher action:
  ```yml
  uses: zyplux/.github/.github/workflows/org_gate_base.yml@main
  ```
