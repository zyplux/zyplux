# 1. [Using test fakes](1-test-fakes.test.ts)

## 1.1 running a CLI

### 1.1.1 a CLI runner captures output and reports the requested exit code

A CLI runner forwards arguments, captures console output, and reports the exit code requested by the command. Console matchers explain missing output.

## 1.2 routing network requests

### 1.2.1 fetch routing accepts URL and Request inputs and restores the real fetch

Fetch routes accept strings, URLs, and Request objects, record requests, and choose the last matching route. Restoring the fake reinstates the original fetch function.

## 1.3 requiring shell mock setup

### 1.3.1 a shell fake explains the required mock when its module is unmocked

Installing a shell fake without the required Vitest module mock reports which Node module needs setup.

## 1.4 answering terminal questions

### 1.4.1 records questions and answers with an empty string

A prompt fake records each terminal question and immediately answers with an empty string, simulating Enter without typed input.
