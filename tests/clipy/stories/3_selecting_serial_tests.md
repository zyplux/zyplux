# 3. [Selecting serial tests](test_3_selecting_serial_tests.py)

## 3.1 running PTY tests outside worker processes

### 3.1.1 runs only deferred tests selected by the current invocation

The serial pass runs only tests selected in the current invocation. A previous full run cannot add PTY tests to a later filtered run.

### 3.1.2 runs a selected serial test without coverage and reports success

Selecting a serial test runs it once outside the worker pool, preserves `--no-cov`, and exits successfully when it passes.

### 3.1.3 propagates failures from serial or parallel tests

A failure in either pass makes the complete invocation fail, including when the other pass succeeds.

### 3.1.4 collects coverage only for the serial test package

The serial pass measures Clipy's PTY tests and appends their coverage to the worker results. Packages tested in workers retain their coverage without being measured again in the serial pass.
