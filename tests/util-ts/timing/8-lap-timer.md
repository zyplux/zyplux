# 8. [Measuring operations and nested timings](8-lap-timer.test.ts)

## 8.1 measuring operations and nested timings

### 8.1.1 laps can contain independently measured concurrent work

### 8.1.2 parallel laps can contain nested operation arrays

### 8.1.3 a measured operation retains its duration when it fails

### 8.1.4 a failed parallel lap waits for its remaining work before returning

### 8.1.5 parallel laps report every failure, including synchronous ones

### 8.1.6 function laps can overlap without sharing timing state

### 8.1.7 stopping a nested marker timer returns its parent

### 8.1.8 console formatting prints every level of nested timings

### 8.1.9 imported timings stay grouped without changing elapsed time

### 8.1.10 timings can be imported directly from entry arrays and iterators
