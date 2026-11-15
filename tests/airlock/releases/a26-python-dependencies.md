# a26. [Publishing Python workspace dependencies](a26_python_dependencies_test.py)

## a26.1 waiting for dependency publications

### a26.1.1 waits for complete dependency artifacts before uploading the inspected build

### a26.1.2 blocks a missing dependency without blocking unrelated releases

### a26.1.3 checks dependencies for optional and conditional installations

### a26.1.4 propagates registry authentication failures before upload

## a26.2 validating built dependency metadata

### a26.2.1 ignores dependencies that do not use a configured workspace version

### a26.2.2 rejects invalid wheel metadata while preparing

### a26.2.3 rejects self dependencies before upload

## a26.3 validating publication cycles

### a26.3.1 rejects cycles before waiting and keeps unrelated jobs independent

### a26.3.2 allows an existing publication to break a dependency cycle

### a26.3.3 includes optional dependencies in cycle detection
