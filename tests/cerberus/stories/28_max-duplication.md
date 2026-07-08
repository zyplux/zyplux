# 28. [Capping copy-paste duplication via jscpd](test_28_max-duplication.py)

## 28.1 enforcing the duplication threshold from jscpd's exit code

### 28.1.1 passes when jscpd stays under the duplication threshold

### 28.1.2 fails with jscpd's verdict when the threshold is exceeded

### 28.1.3 fails with the exit code when jscpd emits no verdict line

### 28.1.4 errors when bunx is not on PATH

## 28.2 sourcing the threshold and file selection from cerberus configuration

### 28.2.1 runs jscpd at the repo root with the default selection and threshold

### 28.2.2 passes a configured threshold through to jscpd

### 28.2.3 passes a configured pattern and ignore through to jscpd
