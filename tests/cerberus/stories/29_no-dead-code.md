# 29. [Banning dead code and complexity offenders via fallow](test_29_no-dead-code.py)

## 29.1 scoping the check

### 29.1.1 skips repos with no package.json without running fallow

## 29.2 enforcing fallow's dead-code verdict

### 29.2.1 passes when both fallow analyses exit clean

### 29.2.2 runs fallow dead code and health non-interactively at the repo root

### 29.2.3 fails with the issue count when fallow dead-code reports issues

### 29.2.4 errors when bunx is not on PATH

## 29.3 enforcing fallow's complexity thresholds

### 29.3.1 fails listing each function fallow health flags above its thresholds

## 29.4 surfacing the measured issue count

### 29.4.1 reports the combined fallow issue count
