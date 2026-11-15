# cz9. [Pushing a branch and advancing its draft PR](cz9-push-branch.test.ts)

## cz9.1 validating preconditions

### cz9.1.1 rejects --hold without --ready

### cz9.1.2 rejects a detached HEAD

### cz9.1.3 refuses to run on main

## cz9.2 cleaning up after a merged PR

### cz9.2.1 switches to main and deletes the local branch once its PR is merged

## cz9.3 pushing and opening a new draft PR

### cz9.3.1 pushes the branch and opens a draft PR when none exists yet

### cz9.3.2 rejects a push that does not land on the expected head

## cz9.4 flipping an already-ready PR to draft before pushing

### cz9.4.1 refreshes an unchanged PR through its required checks

### cz9.4.2 pushes between the draft and ready transitions

### cz9.4.3 rejects when the PR never reports draft state

## cz9.5 flipping a draft PR back to ready

### cz9.5.1 flips an existing draft PR to ready after pushing

### cz9.5.2 holds auto-merge when --hold is set

### cz9.5.3 rejects when the PR never returns to ready state

## cz9.6 merging a ready PR

### cz9.6.1 merges immediately when the merge state is clean

### cz9.6.2 rejects a dirty merge state

### cz9.6.3 schedules auto-merge for any other mergeable state

### cz9.6.4 rejects when the merge state stays UNKNOWN

Check at most ten times, one second apart, to allow GitHub to calculate mergeability.
