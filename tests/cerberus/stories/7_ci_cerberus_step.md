# 7. [Requiring a ci workflow to run cerberus](test_7_ci_cerberus_step.py)

## 7.1 recognizing a working cerberus step in ci

### 7.1.1 passes when a step runs cerberus via uv run or the published uvx package

## 7.2 flagging repos that never run cerberus

### 7.2.1 fails when workflow steps exist but none run cerberus

### 7.2.2 fails when the repo has no ci workflows at all

## 7.3 handling unreadable ci workflows

### 7.3.1 errors when a workflow file is not valid yaml
