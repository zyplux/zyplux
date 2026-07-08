# 10. [Cutting releases for every bumped target](10-release-bumped-targets.test.ts)

## 10.1 validating preconditions

### 10.1.1 refuses to run anywhere but main

### 10.1.2 refuses to run with a dirty working tree

### 10.1.3 refuses to run when local main is behind or ahead of origin/main

## 10.2 selecting which targets to release

### 10.2.1 skips a target whose version is already published

### 10.2.2 skips a target that already has a github release

## 10.3 publishing a pending target

### 10.3.1 cuts a release, watches its workflow to success, and confirms registry visibility

### 10.3.2 rejects when the publish workflow finishes unsuccessfully, rolling back the release

### 10.3.3 rejects when the publish workflow never starts, rolling back the release

### 10.3.4 rejects when the publish workflow never completes, rolling back the release

### 10.3.5 warns instead of failing when the registry never shows the new version, without rolling back

### 10.3.6 keeps polling while the run list is still empty instead of watching a phantom run

### 10.3.7 rejects when the workflow completes without reporting a conclusion, rolling back the release

## 10.4 publishing multiple pending targets

### 10.4.1 publishes all pending targets concurrently, each watching its own tagged workflow run

### 10.4.2 keeps publishing the remaining targets when one fails and reports the failure at the end

### 10.4.3 reports failures in manifest order even when a later target fails first
