# 24. [Enforcing the Python library test seam](test_24_lib_py_test_seam.py)

## 24.1 scoping the check to libraries

### 24.1.1 skips repos with no python packages

### 24.1.2 skips workspaces with no library

### 24.1.3 treats a package with an empty project scripts table as a library

## 24.2 requiring story tests to import only the root module

### 24.2.1 passes a story test importing only public names of the root module

### 24.2.2 fails a story test with a relative import

### 24.2.3 fails a story test importing a deep submodule

### 24.2.4 fails a story test importing a non public name from the root module

### 24.2.5 allows a story test to import a third party module directly

### 24.2.6 passes a disallowed import guarded under type checking

### 24.2.7 passes a disallowed import guarded under a dotted type checking attribute

### 24.2.8 fails a story test with a bare import of a deep submodule

### 24.2.9 passes a story test importing an annotated top level constant from the root module

## 24.3 scoping to a package's own story tests

### 24.3.1 skips cleanly when a package has no story test files yet
