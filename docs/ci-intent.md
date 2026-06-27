# PR Gate Perfect World

## Invariant Rules

### human approvals

- not required except for files marked with CODEOWNERS

### ci

- auto-run on every push to the PR branch
- is a mandatory check for merge into main

### copilot_code_review

- only run on "ready" PRs
- auto-run on every push to the PR branch
- is a mandatory check for merge into main

### review comments

- must be resolved prior to merge into main

### auto-merge

Should trigger when since the latest push to the PR branch:
- ci passed
- copilot_code_review has completed
- no unresolved copilot_code_review comments remain

New pushes invalidate both ci and copilot_code_review.

### skill

- /resolve-pr-review-comments [skill](/home/srg/.claude/skills/resolve-pr-review-comments/SKILL.md) should run in a loop once triggered: should flip PR to draft, assess copilot comments, fix relevant ones, run `just pr` to push fixes changes, respond to all comments and resolve threads, flip pr to ready. Repeat this untill copilot has reviewed with zero comments.

## Observations

- using an action to add @Copilot to the reviewers doesn't start the copilot_code_review - it needs to be manually triggered in using
- copilot_code_review is requested and auto-starts when PR is marked as ready for review after a new push AND branch policy has automatic copilot_code_review setting
- Copilot reviews are comment-only: they never count as approvals and never block merge natively (per GitHub docs)
- the native `copilot-pull-request-reviewer` check-run shows up in the REST `commits/{sha}/check-runs` API but is excluded from the PR status rollup, so it can never satisfy a required status check — it stays "Expected" forever and blocks the PR
- the Copilot check-run and review are produced by the `github-actions` app using `GITHUB_TOKEN`; GitHub never starts a workflow from an event triggered by `GITHUB_TOKEN` (recursion prevention), so the mirror cannot be driven by Copilot's `check_run` (or `pull_request_review`) completion — those events fire no workflow at all

## Implementation

The invariants map onto enforceable GitHub mechanisms as follows:

- `ci` mandatory — required status check (`ci`), `strict_required_status_checks_policy` ties it to the latest push.
- `copilot_code_review` mandatory — cannot be required natively (see Observations). The `copilot-review-gate` workflow triggers on `pull_request` (a human-initiated event that reliably fires, unlike the `GITHUB_TOKEN`-suppressed Copilot events), waits for the `copilot-pull-request-reviewer` check-run to complete, and mirrors its conclusion onto a `copilot-review-complete` commit status (rollup-visible), which the ruleset requires. Each push is a fresh SHA with no status yet, so the required check is unsatisfied until the mirror posts again — this is what invalidates it per push.
- no unresolved review comments — `required_review_thread_resolution`.
- human approvals only for CODEOWNERS files — `require_code_owner_review`, `required_approving_review_count: 0`, `require_last_push_approval: false`.

## Operating

Re-triggering Copilot on a new commit requires the push to land _inside_ the draft→ready cycle: `cz push-branch --ready` (`just pr`) flips the PR to draft, pushes, then flips it back to ready, and that ready transition is what requests a fresh Copilot review. Pre-pushing the branch first makes the in-cycle push a no-op — no `synchronize`/`review_requested` event fires and Copilot stays silent. `cz push-branch --ready` guards against this: on an already-ready PR it compares local `HEAD` to the remote tip and errors when there is nothing to push, so the failure is loud instead of a silently un-reviewed PR.

The mirror is driven by the `pull_request` event rather than Copilot's completion: the Copilot check-run and review are created by the `github-actions` app via `GITHUB_TOKEN`, and `GITHUB_TOKEN`-triggered events never start a workflow, so a `check_run`/`pull_request_review` mirror would never fire. The gate workflow instead triggers on the human-initiated `pull_request` event and polls the check-runs API until Copilot finishes. Because `pull_request` workflows run from the PR branch's own copy, the gate takes effect in the PR that introduces it — no default-branch bootstrap is needed.

## Notes

I am flexible in terms of how the above is implemented, as long as it fits the above criteria.
I think we need to flip PR back to "draft" once copilot_code_review is finished and comments are produced. Then, after a new push and conversion to "ready" copilot_code_review will re-trigger.
I think `just pr` should do the flip to draft -> push -> flip to ready.
copilot_code_review is currently enabled via [org wide branch policy](../.github/rulesets/default-branch-baseline.json)
