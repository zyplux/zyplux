# 19. [Publishing GitHub Actions](19-action-releases.test.ts)

## 19.1 publishing versioned action releases

### 19.1.1 creates reviewed release notes before advancing the major alias

### 19.1.2 repairs a missing alias when the fixed release already exists

### 19.1.3 leaves a completed release unchanged

### 19.1.4 retries an older release using the newest stable release in its major across all pages

### 19.1.5 selects incomplete action releases for workflow retries

### 19.1.6 promotes the commit behind an annotated versioned tag

### 19.1.7 waits for a newly created release to appear before advancing its alias

## 19.2 rejecting incomplete or racing publications

### 19.2.1 requires a published stable release before moving its alias

### 19.2.2 leaves the alias unchanged when GitHub release creation fails

### 19.2.3 reports a rejected tag lease instead of forcing over a concurrent publisher

### 19.2.4 refuses to publish a floating alias to a changed versioned tag

### 19.2.5 rejects invalid action versions before creating a release

### 19.2.6 rejects a missing versioned tag instead of guessing the current commit

## 19.3 preparing action versions through Changesets

### 19.3.1 synchronizes the private manifest, native helper and lockfiles without a PyPI target
