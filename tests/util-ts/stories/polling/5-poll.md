# 5. [Polling a probe until the condition matches](5-poll.test.ts)

## 5.1 polling until the expected result arrives

### 5.1.1 returns an immediate match without sleeping

### 5.1.2 retries defined results that do not match

### 5.1.3 defaults to five attempts one second apart without a final sleep

### 5.1.4 accepts attempt and interval overrides

### 5.1.5 accepts any defined result when no condition is supplied

### 5.1.6 matches falsy expected values

### 5.1.7 propagates probe failures without retrying

### 5.1.8 retries while the result equals the supplied value

### 5.1.9 exhausts attempts while the result stays equal

### 5.1.10 can wait until the result is undefined

### 5.1.11 handles falsy while values and stops on a different undefined result

### 5.1.12 throws the expiry message on exhaustion without a final sleep

### 5.1.13 treats an empty expiry message as required polling

### 5.1.14 returns the defined result from a required lookup

### 5.1.15 accepts an until predicate over the resolved probe result

### 5.1.16 accepts a while predicate and returns a falsy result

### 5.1.17 returns a completed failure for the caller to check

### 5.1.18 propagates predicate errors without replacing them with the expiry message
