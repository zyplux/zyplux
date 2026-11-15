# s1. [Using test fakes](s1-test-fakes.test.ts)

## s1.1 running a CLI

### s1.1.1 a CLI runner captures output and reports the requested exit code

A CLI runner forwards arguments, captures console output, and reports the exit code requested by the command. Console matchers explain missing output.

## s1.2 routing network requests

### s1.2.1 fetch routing accepts URL and Request inputs and restores the real fetch

Fetch routes accept strings, URLs, and Request objects, record requests, and choose the last matching route. Restoring the fake reinstates the original fetch function.

## s1.3 requiring shell mock setup

### s1.3.1 a shell fake explains the required mock when its module is unmocked

Installing a shell fake without the required Vitest module mock reports which Node module needs setup.

## s1.4 answering terminal questions

### s1.4.1 records questions and answers with an empty string

A prompt fake records each terminal question and immediately answers with an empty string, simulating Enter without typed input.
