# 8. [Requiring ci.yml to run the canonical check sequence](test_8_ci_check_sequence.py)

## 8.1 scoping the check to repos with a js or python manifest

### 8.1.1 skips repos with no package json or pyproject manifest

## 8.2 requiring a ci workflow file to exist and parse cleanly

### 8.2.1 fails when no ci workflow file exists

### 8.2.2 errors when the ci workflow is not a valid yaml mapping

## 8.3 requiring the python pipeline to run every step in canonical order

### 8.3.1 passes a python ci workflow that runs every required step in order

### 8.3.2 fails when a required python step is missing or does not match its required command

### 8.3.3 fails when the required python steps run out of canonical order

## 8.4 requiring the typescript pipeline to run every step in canonical order

### 8.4.1 passes a ts ci workflow that runs every required step in order

### 8.4.2 fails when a required ts step is missing or does not match its required command

### 8.4.3 fails when the required ts steps run out of canonical order

## 8.5 matching only commands that actually run

### 8.5.1 fails when a required step appears only in a comment

### 8.5.2 requires canonical commands at command boundaries

### 8.5.3 checks order using the canonical invocation

### 8.5.4 requires one canonical command per ci step

### 8.5.5 rejects skipped background or chained commands

### 8.5.6 rejects pyrefly warning threshold overrides

## 8.6 selecting steps from source files

### 8.6.1 requires install and markdown checks for tooling only manifests

### 8.6.2 requires python quality steps for stub only packages

### 8.6.3 requires typescript quality steps for executable tool configuration

### 8.6.4 does not require prettier for javascript tool configuration

## 8.7 Requiring shared package manager setup

### 8.7.1 accepts both locked installs from the shared action

### 8.7.2 requires the shared action even with a manual frozen install

### 8.7.3 requires shared setup before quality checks

### 8.7.4 requires unconditional successful setup

### 8.7.5 requires setup and checks in the guarded ci job

### 8.7.6 requires root checkout before shared setup

### 8.7.7 accepts a ci display name on another job id

### 8.7.8 accepts explicit root checkout paths

### 8.7.9 rejects ci job prerequisites

## 8.8 Skipping draft pull requests

### 8.8.1 accepts the exact draft guard with optional expression delimiters

### 8.8.2 rejects missing or unrelated ci job conditions

### 8.8.3 rejects failure tolerance in the guarded ci job

### 8.8.4 requires pull request events for draft transitions

### 8.8.5 requires workflow cancellation for the same pull request

### 8.8.6 requires successful unconditional checks inside the guarded job

### 8.8.7 rejects pull request target alongside pull request
