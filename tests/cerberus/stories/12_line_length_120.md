# 12. [Requiring ruff and prettier to agree on line length](test_12_line_length_120.py)

## 12.1 requiring at least one of ruff or prettier to be configured

### 12.1.1 skips repos with neither a ruff nor a prettier config

### 12.1.2 passes when only a ruff config is present and correct

### 12.1.3 passes when only a prettier config is present and correct

## 12.2 requiring ruff to set the standard line length

### 12.2.1 fails when ruff sets a different line length

### 12.2.2 fails when ruff does not set a line length

## 12.3 requiring prettier to set the standard line length

### 12.3.1 fails when prettier sets a different line length

### 12.3.2 fails when prettier does not set a line length

## 12.4 passing a fully compliant setup

### 12.4.1 passes when ruff and prettier both match the standard
