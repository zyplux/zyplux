# 6. [Requiring a strict, unrelaxed pyrefly config](test_6_pyrefly.py)

## 6.1 scoping the check to python repos with source

### 6.1.1 skips repos with no pyproject file

### 6.1.2 skips repos with a pyproject file but no python source

## 6.2 requiring the pyrefly config to be standalone

### 6.2.1 fails when pyrefly config is missing

### 6.2.2 fails when pyrefly config lives in pyproject instead

### 6.2.3 errors when pyrefly config cannot be parsed

## 6.3 requiring the strict preset

### 6.3.1 fails when preset is not strict

## 6.4 covering every production and test root

### 6.4.1 fails and names the uncovered production root

### 6.4.2 fails and names the uncovered test root

## 6.5 forbidding top level relaxations

### 6.5.1 fails when top level errors weaken strict for all code

### 6.5.2 fails when an error kind is set stray at the top level

## 6.6 constraining sub config entries

### 6.6.1 fails when a sub config weakens strict for production or test code

### 6.6.2 fails when a sub config entry is not a table

## 6.7 passing a fully compliant config

### 6.7.1 passes when preset is strict coverage is complete and relaxations are absent
