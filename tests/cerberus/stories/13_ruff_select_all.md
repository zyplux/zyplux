# 13. [Requiring a standalone, strict, minimally-relaxed ruff config](test_13_ruff_select_all.py)

## 13.1 scoping the check to python repos

### 13.1.1 skips repos with no pyproject file

## 13.2 requiring the ruff config to be standalone

### 13.2.1 fails when the ruff config file is missing

### 13.2.2 fails when the ruff config lives in pyproject instead

### 13.2.3 errors when the ruff config cannot be parsed

## 13.3 requiring preview mode

### 13.3.1 fails unless preview is explicitly true

## 13.4 requiring every rule to be selected

### 13.4.1 fails unless lint select is exactly all

## 13.5 keeping top level rule ignores within the sanctioned set

### 13.5.1 passes when only some sanctioned rules are ignored

### 13.5.2 fails and names the rule when an ignore falls outside the sanctioned set

## 13.6 keeping test file relaxations within the sanctioned test set

### 13.6.1 passes when there are no per file ignores

### 13.6.2 passes when only some sanctioned test rules are relaxed

### 13.6.3 passes regardless of which glob names the test files

### 13.6.4 fails and names the rule when a test relaxation falls outside the sanctioned set

## 13.7 passing a fully compliant config

### 13.7.1 passes when preview select and both ignore sets are fully compliant
