# 10. [Requiring TypeScript typecheck to run via project references](test_10_tsc_project_references.py)

## 10.1 scoping the check to typescript workspaces with project references

### 10.1.1 skips repos with no package json

### 10.1.2 skips repos whose package json is not a workspace

### 10.1.3 skips workspaces with no tsconfig file

## 10.2 requiring the typecheck script to build via project references

### 10.2.1 fails when the typecheck script is missing or blank

### 10.2.2 fails when the typecheck script does not build via project references

### 10.2.3 passes when the typecheck script builds via project references
