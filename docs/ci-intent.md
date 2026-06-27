# PR Gate Perfect World

## Invariant Rules

### human approvals

- not required except for files marked with CODEOWNERS

### ci

- auto-run on every push to the PR branch
- is a mandatory check for merge into main

### copilot_code_review

- only run on "read" PRs
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

## Notes

Because copilot_code_review is a mandatory check and comments must be resolved - it blocks the merge like a ci.
I am flexible in terms of how the above is implemented, as long as it fits the above criteria.

## Observations

- using an action to add @Copilot to the reviewers doesn't start the copilot_code_review - it needs to be manually triggered in using
- copilot_code_review is requested and auto-starts when PR is marked as ready for review the first time AND branch policy has automatic copilot_code_review setting
