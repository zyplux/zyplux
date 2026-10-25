# 26. [Publishing Python workspace dependencies](test_26_python_dependencies.py)

## 26.1 waiting for dependency publications

### 26.1.1 waits for complete dependency artifacts before uploading the inspected build

### 26.1.2 blocks a missing dependency without blocking unrelated releases

### 26.1.3 checks dependencies for optional and conditional installations

### 26.1.4 propagates registry authentication failures before upload

## 26.2 validating built dependency metadata

### 26.2.1 ignores dependencies that do not use a configured workspace version

### 26.2.2 rejects invalid wheel metadata before upload

### 26.2.3 rejects self dependencies before upload

## 26.3 validating publication cycles

### 26.3.1 rejects cycles before waiting and keeps unrelated jobs independent

### 26.3.2 allows an existing publication to break a dependency cycle

### 26.3.3 includes optional dependencies in cycle detection

### 26.3.4 requires dynamic workspace dependencies to publish first
