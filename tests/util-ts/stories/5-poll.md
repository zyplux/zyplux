# 5. [Polling a probe until it succeeds](5-poll.test.ts)

## 5.1 polling a probe until it returns a defined value

1. 5.1.1 returns the first defined result without retrying
2. 5.1.2 retries after undefined results until the probe returns a value
3. 5.1.3 returns undefined once every attempt is exhausted

### 5.1.4 waits intervalMs between attempts
