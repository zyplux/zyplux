# 23. [Enforcing the Python cli test seam](test_23_cli-py-tests.py)

## 23.1 scoping the check to cli apps

### 23.1.1 skips repos with no python packages

### 23.1.2 skips workspaces with no cli app

## 23.2 resolving a package's root module

### 23.2.1 resolves the root module from build backend module name

### 23.2.2 resolves the root module from the shallowest init file when module name is absent

### 23.2.3 errors when the root module cannot be resolved

## 23.3 requiring story tests to import only the seam

### 23.3.1 passes a story test importing only public names of the root module

### 23.3.2 passes a story test importing public names of the cli entry module

### 23.3.3 fails a story test with a relative import

### 23.3.4 fails a story test importing a deep submodule

### 23.3.5 fails a story test importing a non public name from the root module

### 23.3.6 allows a story test to import a third party module directly

### 23.3.7 passes a disallowed import guarded under type checking

### 23.3.8 does not exempt an import in the else branch of a type checking guard

### 23.3.9 restricts the public surface to a declared all list

### 23.3.10 does not exempt a guard on a custom non typing type checking attribute

### 23.3.11 resolves a nested cli entry module over a shallower decoy with the same basename

## 23.4 scoping to a package's own story tests

### 23.4.1 skips cleanly when a package has no story test files yet
