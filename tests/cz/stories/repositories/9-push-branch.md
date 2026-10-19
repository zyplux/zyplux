# 9. [Pushing a branch and advancing its draft PR](9-push-branch.test.ts)

## 9.1 validating preconditions

### 9.1.1 rejects --hold without --ready

### 9.1.2 rejects a detached HEAD

### 9.1.3 refuses to run on main

## 9.2 cleaning up after a merged PR

### 9.2.1 switches to main and deletes the local branch once its PR is merged

## 9.3 pushing and opening a new draft PR

### 9.3.1 pushes the branch and opens a draft PR when none exists yet

### 9.3.2 rejects a push that does not land on the expected head

## 9.4 flipping an already-ready PR to draft before pushing

### 9.4.1 refreshes an unchanged PR through its required checks

### 9.4.2 pushes between the draft and ready transitions

### 9.4.3 rejects when the PR never reports draft state

## 9.5 flipping a draft PR back to ready

### 9.5.1 flips an existing draft PR to ready after pushing

### 9.5.2 holds auto-merge when --hold is set

### 9.5.3 rejects when the PR never returns to ready state

## 9.6 merging a ready PR

### 9.6.1 merges immediately when the merge state is clean

### 9.6.2 rejects a dirty merge state

### 9.6.3 schedules auto-merge for any other mergeable state

### 9.6.4 rejects when the merge state stays UNKNOWN

Check at most ten times, one second apart, to allow GitHub to calculate mergeability.
