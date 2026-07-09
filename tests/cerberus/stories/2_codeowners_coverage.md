# 2. [Requiring CODEOWNERS to cover /.github/](test_2_codeowners_coverage.py)

## 2.1 requiring a codeowners file with ownership rules to exist

### 2.1.1 fails when no codeowners file exists in any recognized location

### 2.1.2 passes when the codeowners file exists in an alternate recognized location

### 2.1.3 fails when the codeowners file has no ownership rules

## 2.2 requiring the file to cover the github directory

### 2.2.1 passes when a rule explicitly owns the github directory

### 2.2.2 passes when a wildcard rule owns everything

### 2.2.3 fails when only a lookalike github path is owned
