# 3. [Waiting for test conditions](3-test-polling.test.ts)

## 3.1 waiting for conditions

### 3.1.1 polling settles after a matching observation without a grace period

Polling retries until the condition matches and returns a settled outcome.

### 3.1.2 polling aborts a read that does not finish before the deadline

The deadline bounds pending observations, aborts their signal, and returns an unsettled outcome with an error.

### 3.1.3 a matching observation must survive the grace period

A grace period requires a second matching observation after the delay; a mismatch resumes polling.

### 3.1.4 the deadline also bounds the grace period

Polling expires when its deadline arrives during a grace period.
