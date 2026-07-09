# 3. [Requiring a working ci workflow](test_3_ci_workflow_gate.py)

## 3.1 requiring the workflow file to exist and parse cleanly

### 3.1.1 fails when no workflow file exists

### 3.1.2 errors on invalid yaml

### 3.1.3 errors when the workflow is not a mapping

### 3.1.4 passes when the workflow lives at the yaml extension

## 3.2 requiring a job that satisfies the ci status check

### 3.2.1 fails without a job named ci

### 3.2.2 passes when a job id is named ci

### 3.2.3 passes when a job name field is ci

## 3.3 requiring the workflow to trigger on pull requests

### 3.3.1 fails without a pull request trigger

### 3.3.2 passes with a pull request or pull request target trigger

### 3.3.3 passes when the on key parses to a boolean
