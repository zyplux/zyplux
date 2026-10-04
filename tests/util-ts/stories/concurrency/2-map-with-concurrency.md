# 2. [Mapping over items with a fixed worker limit](2-map-with-concurrency.test.ts)

## 2.1 mapping items concurrently while preserving output order

### 2.1.1 maps each item to its result in original order even when tasks settle out of order

### 2.1.2 never runs more tasks concurrently than the configured limit

### 2.1.3 returns an empty array immediately for empty input

## 2.2 validating the concurrency limit argument

### 2.2.1 rejects a limit that is not a positive integer

## 2.3 propagating task failures

### 2.3.1 rejects with the task error when any task fails
