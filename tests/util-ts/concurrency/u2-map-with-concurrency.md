# u2. [Mapping over items with a fixed worker limit](u2-map-with-concurrency.test.ts)

## u2.1 mapping items concurrently while preserving output order

### u2.1.1 maps each item to its result in original order even when tasks settle out of order

### u2.1.2 never runs more tasks concurrently than the configured limit

### u2.1.3 returns an empty array immediately for empty input

## u2.2 validating the concurrency limit argument

### u2.2.1 rejects a limit that is not a positive integer

## u2.3 propagating task failures

### u2.3.1 rejects with the task error when any task fails
