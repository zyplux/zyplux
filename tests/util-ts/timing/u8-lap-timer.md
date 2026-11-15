# u8. [Measuring operations and nested timings](u8-lap-timer.test.ts)

## u8.1 measuring operations and nested timings

### u8.1.1 laps can contain independently measured concurrent work

### u8.1.2 parallel laps can contain nested operation arrays

### u8.1.3 a measured operation retains its duration when it fails

### u8.1.4 a failed parallel lap waits for its remaining work before returning

### u8.1.5 parallel laps report every failure, including synchronous ones

### u8.1.6 function laps can overlap without sharing timing state

### u8.1.7 stopping a nested marker timer returns its parent

### u8.1.8 console formatting prints every level of nested timings

### u8.1.9 imported timings stay grouped without changing elapsed time

### u8.1.10 timings can be imported directly from entry arrays and iterators
