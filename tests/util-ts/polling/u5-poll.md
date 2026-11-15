# u5. [Polling a probe until the condition matches](u5-poll.test.ts)

## u5.1 polling until the expected result arrives

### u5.1.1 returns an immediate match without sleeping

### u5.1.2 retries defined results that do not match

### u5.1.3 defaults to five attempts one second apart without a final sleep

### u5.1.4 accepts attempt and interval overrides

### u5.1.5 accepts any defined result when no condition is supplied

### u5.1.6 matches falsy expected values

### u5.1.7 propagates probe failures without retrying

### u5.1.8 retries while the result equals the supplied value

### u5.1.9 exhausts attempts while the result stays equal

### u5.1.10 can wait until the result is undefined

### u5.1.11 handles falsy while values and stops on a different undefined result

### u5.1.12 throws the expiry message on exhaustion without a final sleep

### u5.1.13 treats an empty expiry message as required polling

### u5.1.14 returns the defined result from a required lookup

### u5.1.15 accepts an until predicate over the resolved probe result

### u5.1.16 accepts a while predicate and returns a falsy result

### u5.1.17 returns a completed failure for the caller to check

### u5.1.18 propagates predicate errors without replacing them with the expiry message
