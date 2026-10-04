# 10. [Cutting releases for every bumped target](10-release-bumped-targets.test.ts)

## 10.1 validating preconditions

### 10.1.1 refuses to run anywhere but main

### 10.1.2 refuses to run with a dirty working tree

### 10.1.3 refuses to run when local main is behind or ahead of origin/main

## 10.2 selecting which targets to release

### 10.2.1 skips a target whose version is already published

### 10.2.2 skips a target that already has a github release

### 10.2.3 stops before creating releases when the release lookup fails

## 10.3 publishing a pending target

Once a release is created, its release and tag remain available if watching fails, times out, or reports an unsuccessful workflow. The command reports each failed target once. Inspect Actions before retrying; publishing may already have completed some steps.

### 10.3.1 cuts a release, watches its workflow to success, and confirms registry visibility

### 10.3.2 rejects when the publish workflow finishes unsuccessfully, keeping the release and tag

### 10.3.3 rejects when no new publish workflow run is found within the watch window, keeping the release and tag

Check at most 12 times, five seconds apart.

### 10.3.4 rejects when the publish workflow does not report completion within the watch window, keeping the release and tag

Check at most 60 times, ten seconds apart.

### 10.3.5 warns instead of failing when registry checks do not confirm the new version within the watch window

Check at most 12 times, ten seconds apart.

### 10.3.6 keeps polling while the run list is still empty instead of watching a phantom run

### 10.3.7 rejects when the workflow completes without reporting a conclusion, keeping the release and tag

### 10.3.8 reports a workflow read error once while keeping the release and tag

### 10.3.9 waits for completed status and checks the conclusion from the same response

Read status and conclusion together on each attempt, accepting a conclusion only when status is `completed`. An absent conclusion fails immediately; a run that never completes exhausts the watch window.

## 10.4 publishing multiple pending targets

### 10.4.1 publishes all pending targets concurrently, each watching its own tagged workflow run

### 10.4.2 keeps publishing the remaining targets when one fails and reports the failure at the end

### 10.4.3 reports failures in manifest order even when a later target fails first
