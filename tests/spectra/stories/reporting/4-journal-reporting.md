# 4. [Recording test runs in the journal](4-journal-reporting.test.ts)

## 4.1 recording test runs

### 4.1.1 a shared test run records each project and closes its journal streams

The reporter records summaries, test failures, setup failures, and console output through the journal stream protocol. Named projects have separate identifiers; unnamed projects use the configured identifier. Streams close when the test run finishes.

## 4.2 handling an unavailable journal

### 4.2.1 an unavailable journal leaves the test runner usable

When its journal socket is absent, the reporter leaves ordinary test execution usable without reporting connection failures.

### 4.2.2 a journal connection failure is reported without changing the test outcome

An explicitly enabled reporter reports socket connection failures to the console while allowing the test runner to finish.
