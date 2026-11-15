# p1. [Workspace setup](p1_setup_plan_test.py)

## p1.1 Reading workspace pins

### p1.1.1 prepares both toolchains from workspace pins

### p1.1.2 accepts the minimum supported pnpm

### p1.1.3 prepares only the selected package manager

## p1.2 Rejecting unsupported setup

### p1.2.1 requires both workspaces and lockfiles before bootstrapping

### p1.2.2 requires exact versions for executable cache keys

### p1.2.3 requires a pnpm package manager

### p1.2.4 requires a node runtime

### p1.2.5 rejects package manager integrity suffixes

### p1.2.6 rejects pnpm without runtime install control

### p1.2.7 rejects unknown or empty package manager selection

## p1.3 GitHub Actions integration

### p1.3.1 writes github action outputs
