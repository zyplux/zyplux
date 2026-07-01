# Next

## Improve resolve-pr-review-comments skill

- reduce verbosity and bloat
- must push back on review comments and verify them, don't just fix blindly, take them with a grain of salt
- if possible, update copilot-instructions with a short concise instruction to prevent future false positives
- last step is supposed to verify, but it's destructive. It should verify first (non-destructive), and only then do `just pr` that will delete local branch, switch to main and pull.
- steps that involve scripting should be codified instead in cs and called via just
- even the polling script like
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
  could be automated

## Fix root README.md

- should describe each workspace member briefly instead

## Consider publishing org_gate_base as action

- this should probably be a watcher action:
  ```yml
  uses: zyplux/.github/.github/workflows/org_gate_base.yml@main
  ```
