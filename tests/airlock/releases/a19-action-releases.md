# a19. [Publishing GitHub Actions](a19_action_releases_test.py)

## a19.1 publishing versioned action releases

### a19.1.1 creates reviewed release notes before advancing the major alias

### a19.1.2 repairs a missing alias when the fixed release already exists

### a19.1.3 leaves a completed release unchanged

### a19.1.4 retries an older release using the newest stable release in its major across all pages

### a19.1.5 selects incomplete action releases for workflow retries

### a19.1.6 promotes the commit behind an annotated versioned tag

### a19.1.7 waits for a newly created release to appear before advancing its alias

## a19.2 rejecting incomplete or racing publications

### a19.2.1 requires a published stable release before moving its alias

### a19.2.2 leaves the alias unchanged when github release creation fails

### a19.2.3 reports a rejected tag lease instead of forcing over a concurrent publisher

### a19.2.4 refuses to publish a floating alias to a changed versioned tag

### a19.2.5 rejects invalid action versions before creating a release

### a19.2.6 rejects a missing versioned tag instead of guessing the current commit

### a19.2.7 rejects action repository overrides

## a19.3 preparing action versions through pnpm

### a19.3.1 synchronizes the private manifest native helper and lockfiles without a pypi target
